#include <ctype.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SLOT_COUNT 8
#define APPROVED_STAMP 0x4c414553u
#ifndef FLAG_PATH
#define FLAG_PATH "/flag"
#endif

typedef struct {
    uint32_t id;
    char label[8];
    uint32_t amendment;
} PublicReceipt;

typedef struct {
    uint32_t id;
    char route[8];
    uint32_t approved;
} SealedReceipt;

_Static_assert(sizeof(PublicReceipt) == 16, "public receipt layout changed");
_Static_assert(sizeof(SealedReceipt) == 16, "sealed receipt layout changed");
_Static_assert(offsetof(PublicReceipt, amendment) == 12, "amendment offset changed");
_Static_assert(offsetof(SealedReceipt, approved) == 12, "approval offset changed");

enum SlotKind { EMPTY, PUBLIC, SEALED };

static unsigned char slots[SLOT_COUNT][sizeof(PublicReceipt)];
static enum SlotKind kinds[SLOT_COUNT];
static uint32_t ids[SLOT_COUNT];
static uint32_t next_id = 1001;

static struct {
    int active;
    unsigned char *target;
    uint32_t amendment;
} pending;

/* A queued amendment deliberately keeps its target when a receipt is cancelled. */
static int read_number(const char *prompt, int base, uint32_t *out)
{
    char line[128];
    size_t length = 0;
    int invalid = 0;
    int ch;

    fputs(prompt, stdout);
    while ((ch = getchar()) != EOF && ch != '\n') {
        if (ch == 0 || length + 1 >= sizeof(line)) {
            invalid = 1;
        } else {
            line[length++] = (char)ch;
        }
    }
    if (ch == EOF && length == 0)
        return -1;
    if (invalid)
        return 0;
    line[length] = '\0';

    char *start = line;
    while (isspace((unsigned char)*start))
        start++;
    if (*start == '-' || *start == '\0')
        return 0;

    errno = 0;
    char *end;
    unsigned long value = strtoul(start, &end, base);
    if (errno == ERANGE || end == start || value > UINT32_MAX)
        return 0;
    while (isspace((unsigned char)*end))
        end++;
    if (*end != '\0')
        return 0;
    *out = (uint32_t)value;
    return 1;
}

static int find_slot(uint32_t id, enum SlotKind kind)
{
    for (int i = 0; i < SLOT_COUNT; i++) {
        if (kinds[i] == kind && ids[i] == id)
            return i;
    }
    return -1;
}

static int free_slot(void)
{
    for (int i = 0; i < SLOT_COUNT; i++) {
        if (kinds[i] == EMPTY)
            return i;
    }
    return -1;
}

static void create_receipt(enum SlotKind kind)
{
    int slot = free_slot();
    if (slot < 0 || next_id == UINT32_MAX) {
        puts("No receipt slots available.");
        return;
    }

    uint32_t id = next_id++;
    memset(slots[slot], 0, sizeof(slots[slot]));
    if (kind == PUBLIC) {
        PublicReceipt receipt = { .id = id };
        memcpy(receipt.label, "PUBLIC", 6);
        memcpy(slots[slot], &receipt, sizeof(receipt));
        puts("Public receipt created.");
    } else {
        SealedReceipt receipt = { .id = id };
        memcpy(receipt.route, "SEALED", 6);
        memcpy(slots[slot], &receipt, sizeof(receipt));
        puts("Sealed receipt created; awaiting approval.");
    }
    kinds[slot] = kind;
    ids[slot] = id;
    printf("Receipt ID: %u\n", id);
}

static void queue_amendment(void)
{
    uint32_t id, amendment;
    if (pending.active) {
        puts("The amendment queue is full.");
        return;
    }
    if (read_number("Public receipt ID: ", 10, &id) != 1 ||
        read_number("Amendment (hex): ", 16, &amendment) != 1) {
        puts("Invalid input.");
        return;
    }
    int slot = find_slot(id, PUBLIC);
    if (slot < 0) {
        puts("No such public receipt.");
        return;
    }
    pending.active = 1;
    pending.target = slots[slot] + offsetof(PublicReceipt, amendment);
    pending.amendment = amendment;
    puts("Amendment queued.");
}

static void cancel_public(void)
{
    uint32_t id;
    if (read_number("Public receipt ID: ", 10, &id) != 1) {
        puts("Invalid input.");
        return;
    }
    int slot = find_slot(id, PUBLIC);
    if (slot < 0) {
        puts("No such public receipt.");
        return;
    }
    memset(slots[slot], 0, sizeof(slots[slot]));
    ids[slot] = 0;
    kinds[slot] = EMPTY;
    puts("Public receipt cancelled.");
}

static void process_queue(void)
{
    if (!pending.active) {
        puts("The amendment queue is empty.");
        return;
    }
    memcpy(pending.target, &pending.amendment, sizeof(pending.amendment));
    pending.active = 0;
    pending.target = NULL;
    pending.amendment = 0;
    puts("Amendment processed.");
}

static void export_sealed(void)
{
    uint32_t id;
    if (read_number("Sealed receipt ID: ", 10, &id) != 1) {
        puts("Invalid input.");
        return;
    }
    int slot = find_slot(id, SEALED);
    if (slot < 0) {
        puts("No such sealed receipt.");
        return;
    }
    uint32_t approved;
    memcpy(&approved, slots[slot] + offsetof(SealedReceipt, approved), sizeof(approved));
    if (approved != APPROVED_STAMP) {
        puts("Receipt not approved.");
        return;
    }

    FILE *flag = fopen(FLAG_PATH, "r");
    if (flag == NULL) {
        puts("Export unavailable.");
        return;
    }
    int ch, last = '\n';
    while ((ch = fgetc(flag)) != EOF) {
        putchar(ch);
        last = ch;
    }
    if (last != '\n')
        putchar('\n');
    fclose(flag);
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    for (;;) {
        puts("\n1. Create public receipt\n2. Queue amendment\n3. Cancel public receipt\n4. Create sealed receipt\n5. Process queue\n6. Export sealed receipt\n7. Exit");
        uint32_t choice;
        int result = read_number("Choice: ", 10, &choice);
        if (result < 0)
            return 0;
        if (result == 0) {
            puts("Invalid choice.");
            continue;
        }
        switch (choice) {
        case 1: create_receipt(PUBLIC); break;
        case 2: queue_amendment(); break;
        case 3: cancel_public(); break;
        case 4: create_receipt(SEALED); break;
        case 5: process_queue(); break;
        case 6: export_sealed(); break;
        case 7: return 0;
        default: puts("Invalid choice."); break;
        }
    }
}
