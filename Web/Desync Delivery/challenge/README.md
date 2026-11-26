# Desync Delivery

## Event hosting (KCTF)

Run the build script from the challenge root before using KCTF. It validates
the canonical `flag.txt`, prepares the KCTF image and healthcheck inputs, and
creates the player handout (`dis.tar.gz`, containing only the prompt):

```sh
cd ..
./build.sh
kctf chal start
kctf chal status
```

The KCTF manifest exposes HTTPS to gateway port 8080; the edge and backend
listen only on loopback in the challenge image. The KCTF healthcheck runs the
intended solve against the local service and checks the canonical flag. Add the
URL KCTF reports to the competition platform after verifying it anonymously.
Run the local service with `docker compose up --build` from this directory if
needed.

The gateway accepts a normal `POST /intake` and forwards its body as an opaque
byte stream to the edge. The edge and backend retain the intentional
`Content-Length` versus chunked framing mismatch. A crafted inner request can
therefore bypass the edge's authorization marker and retrieve the held parcel
record. The gateway does not change the challenge objective.

## Previous Cloud Run setup

The older Cloud Run URL currently redirects anonymous visitors to Google
sign-in and is **not** a playable endpoint. The files below remain for that
environment, but the event deployment uses KCTF and the root `flag.txt`.

### Flag configuration

The Cloud Run backend reads `FLAG` from the Secret Manager secret
`desync-delivery-flag`. The Cloud Run service account must have
`roles/secretmanager.secretAccessor` on that secret. `cloudrun.yaml` maps the
secret's latest version to the backend's `FLAG` environment variable. Keep
that value equal to `../flag.txt` if this alternate deployment is used.

If the secret has not been created yet, add it once from this directory:

```sh
gcloud secrets create desync-delivery-flag \
  --replication-policy=automatic \
  --data-file=../flag.txt

gcloud secrets add-iam-policy-binding desync-delivery-flag \
  --member=serviceAccount:desync-delivery-runtime@desync-delivery.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Build and deploy

Deploy from this directory:

```sh
gcloud config set project desync-delivery
gcloud builds submit --region=us-east5 --config=cloudbuild.yaml .
gcloud run services replace cloudrun.yaml --region=us-east5
gcloud run services add-iam-policy-binding desync-delivery \
  --region=us-east5 \
  --member=allUsers \
  --role=roles/run.invoker
gcloud run services describe desync-delivery \
  --region=us-east5 \
  --format='value(status.url)'
```

The old service uses image tag `v3`. For a source update, increment `_TAG` in
`cloudbuild.yaml` and update the gateway, edge, and backend image tags in
`cloudrun.yaml` before rebuilding and replacing the service.

## Organizer verification

The solve script is for organizer verification; do not include it in the
player download. After `docker compose up --build`, run it against the local
gateway:

```sh
python3 ../solution/solve.py http://localhost:8080
```
