"""Check legitimate releases, intended exploitation, and rejected shortcuts."""


from support import AppCase, TEST_FLAG


class WorkflowTests(AppCase):
    def test_normal_release(self):
        alias_id = self.alias()
        manifest_id = self.manifest([alias_id])
        base = f"/api/manifests/{manifest_id}"
        self.assertEqual(self.client.post(base + "/snapshot").status_code, 409)
        self.assertEqual(self.client.post(base + "/approve").status_code, 200)
        result = self.client.post(base + "/snapshot")
        self.assertEqual(result.status_code, 200)
        self.assertIn("attachment", result.headers["Content-Disposition"])
        self.assertEqual(result.json["shards"][0]["content"], "feature,label\n0.1,0\n0.9,1\n")
        self.assertNotIn(TEST_FLAG, result.text)

    def test_full_intended_chain(self):
        alias_id = self.alias()
        manifest_id = self.manifest([alias_id])
        base = f"/api/manifests/{manifest_id}"
        manifest = self.client.get(base).json
        approval = self.client.post(base + "/approve").json
        edit = self.client.patch(f"/api/aliases/{alias_id}", json={"target_shard_id": "restricted-v1"})
        self.assertEqual(edit.status_code, 409)
        self.assertEqual(self.client.put(base, json={"alias_ids": [alias_id]}).status_code, 409)
        # Exact-case restore is now blocked by the same lock as PATCH.
        self.assertEqual(self.client.post("/api/aliases/restore", json=self.backup(alias_id)).status_code, 409)
        # The lock test is case-sensitive while the row is matched COLLATE NOCASE.
        restored = self.client.post("/api/aliases/restore", json=self.backup(alias_id.upper()))
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(self.client.get(base).json, manifest)
        self.assertEqual(self.client.get(base + "/approval").json["approval"], approval)
        self.assertEqual(self.client.get(base + "/preview").status_code, 403)
        self.assertEqual(self.client.post(base + "/approve").status_code, 403)
        result = self.client.post(base + "/snapshot")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["shards"][0]["content"], TEST_FLAG)

    def test_restore_lock_is_case_sensitive(self):
        alias_id = self.alias()
        manifest_id = self.manifest([alias_id])
        self.client.post(f"/api/manifests/{manifest_id}/approve")
        # Exact-case restore of a locked alias is refused and leaves the target intact.
        self.assertEqual(self.client.post("/api/aliases/restore", json=self.backup(alias_id)).status_code, 409)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").json["target_shard_id"], "sample-v1")
        # Upper-casing the ID dodges the case-sensitive lock but still updates the real row.
        self.assertEqual(self.client.post("/api/aliases/restore", json=self.backup(alias_id.upper())).status_code, 200)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").json["target_shard_id"], "restricted-v1")

    def test_unlocked_alias_restores_with_exact_case(self):
        alias_id = self.alias()  # not part of any approved manifest
        self.assertEqual(self.client.post("/api/aliases/restore", json=self.backup(alias_id, "sample-v2")).status_code, 200)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").json["target_shard_id"], "sample-v2")

    def test_restricted_first_cannot_be_approved(self):
        manifest_id = self.manifest([self.alias(), self.alias("restricted-v1")])
        base = f"/api/manifests/{manifest_id}"
        preview = self.client.get(base + "/preview")
        self.assertEqual(preview.status_code, 403)
        self.assertNotIn("feature,label", preview.text)
        self.assertNotIn(TEST_FLAG, preview.text)
        self.assertEqual(self.client.post(base + "/approve").status_code, 403)
        self.assertFalse(self.client.get(base + "/approval").json["approved"])
        self.assertEqual(self.client.post(base + "/snapshot").status_code, 409)

    def test_draft_edits_advance_version(self):
        first, second = self.alias(), self.alias("sample-v2")
        manifest_id = self.manifest([first])
        response = self.client.put(f"/api/manifests/{manifest_id}", json={"alias_ids": [second]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["version"], 2)
        self.assertEqual(response.json["alias_ids"], [second])

    def test_invalid_restore_is_atomic(self):
        alias_id = self.alias()
        backup = self.backup(alias_id)
        backup["aliases"].append({"id": "missing", "target_shard_id": "sample-v1"})
        self.assertEqual(self.client.post("/api/aliases/restore", json=backup).status_code, 404)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").json["target_shard_id"], "sample-v1")

    def test_backup_roundtrip(self):
        alias_id = self.alias()
        backup = self.client.get("/api/aliases/backup").json
        self.client.patch(f"/api/aliases/{alias_id}", json={"target_shard_id": "sample-v2"})
        self.assertEqual(self.client.post("/api/aliases/restore", json=backup).status_code, 200)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").json["target_shard_id"], "sample-v1")

    def test_invalid_inputs_and_injected_fields(self):
        for body in [[], {}, {"target_shard_id": []}, {"target_shard_id": ""},
                     {"target_shard_id": "sample-v1", "role": "curator"}]:
            with self.subTest(body=body):
                self.assertIn(self.client.post("/api/aliases", json=body).status_code, (400, 404))
        for ids in [[], "abc", [None], [[]], ["a"] * 21]:
            self.assertEqual(self.client.post("/api/manifests", json={"alias_ids": ids}).status_code, 400)
        alias_id = self.alias()
        self.assertEqual(self.client.post("/api/manifests", json={"alias_ids": [alias_id, alias_id]}).status_code, 400)
        self.assertEqual(self.client.post("/api/manifests", json={"alias_ids": [alias_id], "approved": True}).status_code, 400)
        self.assertEqual(self.client.post("/api/aliases", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/aliases", data="x" * 40000, content_type="application/json").status_code, 413)

    def test_digest_and_version_checks(self):
        manifest_id = self.manifest([self.alias()])
        base = f"/api/manifests/{manifest_id}"
        self.client.post(base + "/approve")
        self.sql("UPDATE approvals SET digest='tampered' WHERE manifest_id=?", (manifest_id,))
        self.assertEqual(self.client.post(base + "/snapshot").status_code, 409)
        self.client.post(base + "/approve")
        self.sql("UPDATE approvals SET version=99 WHERE manifest_id=?", (manifest_id,))
        self.assertEqual(self.client.post(base + "/snapshot").status_code, 409)

    def test_restore_rejects_bad_format_duplicates_and_missing_targets(self):
        alias_id = self.alias()
        for key, value in [("format", "bad"), ("workspace_id", "other"), ("aliases", []),
                           ("aliases", [{"id": [], "target_shard_id": "sample-v1"}])]:
            backup = self.backup(alias_id)
            backup[key] = value
            self.assertEqual(self.client.post("/api/aliases/restore", json=backup).status_code, 400)
        backup = self.backup(alias_id)
        backup["aliases"] *= 2
        self.assertEqual(self.client.post("/api/aliases/restore", json=backup).status_code, 400)
        self.assertEqual(self.client.post("/api/aliases/restore", json=self.backup(alias_id, "missing")).status_code, 404)

    def test_alias_and_manifest_quotas(self):
        aliases = [self.alias() for _ in range(64)]
        self.assertEqual(self.client.post("/api/aliases", json={"target_shard_id": "sample-v1"}).status_code, 429)
        for _ in range(64):
            self.manifest([aliases[0]])
        self.assertEqual(self.client.post("/api/manifests", json={"alias_ids": [aliases[0]]}).status_code, 429)
