#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEADER_SIZE 10
#define MAX_FILE_SIZE 8192
#define MAX_INSTRUCTIONS 255
#define MAX_DECODE_OPS 32
#define VALIDATOR_INSTRUCTION_SIZE 7

static uint32_t read_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint32_t rol32(uint32_t value, unsigned amount) {
    amount &= 31U;
    if (amount == 0) return value;
    return (value << amount) | (value >> (32U - amount));
}

static uint8_t rol8(uint8_t value, unsigned amount) {
    amount &= 7U;
    if (amount == 0) return value;
    return (uint8_t)((value << amount) | (value >> (8U - amount)));
}

static int parse_slot(const char *text, uint8_t *slot) {
    char *end = NULL;
    long value;

    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value < 0 || value > 255) {
        return 0;
    }
    *slot = (uint8_t)value;
    return 1;
}

static int valid_register(uint8_t reg) {
    return reg < 8;
}

static int branch_target(size_t pc, uint32_t raw_offset, size_t count, size_t *target) {
    int64_t offset = (raw_offset & UINT32_C(0x80000000))
                         ? (int64_t)raw_offset - INT64_C(0x100000000)
                         : (int64_t)raw_offset;
    int64_t destination = (int64_t)pc + 1 + offset;
    if (destination < 0 || destination >= (int64_t)count) return 0;
    *target = (size_t)destination;
    return 1;
}

static int run_validator(const uint8_t *code, size_t count,
                         const uint8_t *slots, uint32_t *seed_out) {
    uint32_t regs[8] = {0};
    size_t pc = 0, steps = 0;
    unsigned checks = 0;

    while (pc < count && steps++ < count * 4 + 16) {
        const uint8_t *ins = code + pc * VALIDATOR_INSTRUCTION_SIZE;
        uint8_t op = ins[0], a = ins[1], b = ins[2];
        uint32_t imm = read_u32(ins + 3);
        size_t next = pc + 1;

        switch (op) {
            case 0x10: /* SETI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] = imm;
                break;
            case 0x11: /* INPUT rA, slot */
                if (!valid_register(a) || b >= 4) return 0;
                regs[a] = slots[b];
                break;
            case 0x12: /* MOV rA, rB */
                if (!valid_register(a) || !valid_register(b)) return 0;
                regs[a] = regs[b];
                break;
            case 0x20: /* ADD rA, rB */
                if (!valid_register(a) || !valid_register(b)) return 0;
                regs[a] += regs[b];
                break;
            case 0x21: /* XOR rA, rB */
                if (!valid_register(a) || !valid_register(b)) return 0;
                regs[a] ^= regs[b];
                break;
            case 0x22: /* MUL rA, rB */
                if (!valid_register(a) || !valid_register(b)) return 0;
                regs[a] *= regs[b];
                break;
            case 0x23: /* SUB rA, rB */
                if (!valid_register(a) || !valid_register(b)) return 0;
                regs[a] -= regs[b];
                break;
            case 0x24: /* ROLI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] = rol32(regs[a], imm);
                break;
            case 0x25: /* SHRI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] >>= (imm & 31U);
                break;
            case 0x26: /* ADDI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] += imm;
                break;
            case 0x27: /* XORI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] ^= imm;
                break;
            case 0x28: /* MULI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] *= imm;
                break;
            case 0x29: /* ANDI rA, imm32 */
                if (!valid_register(a)) return 0;
                regs[a] &= imm;
                break;
            case 0x30: /* JZ rA, relative instruction offset */
                if (!valid_register(a)) return 0;
                if (regs[a] == 0 && !branch_target(pc, imm, count, &next)) return 0;
                break;
            case 0x31: /* JNZ rA, relative instruction offset */
                if (!valid_register(a)) return 0;
                if (regs[a] != 0 && !branch_target(pc, imm, count, &next)) return 0;
                break;
            case 0x32: /* JMP relative instruction offset */
                if (!branch_target(pc, imm, count, &next)) return 0;
                break;
            case 0x40: /* CHECK rA, imm32 */
                if (!valid_register(a) || regs[a] != imm) return 0;
                checks++;
                break;
            case 0xFE: /* HALT */
                if (checks != 2) return 0;
                *seed_out = regs[0] ^ rol32(regs[4], 11);
                return 1;
            default:
                return 0;
        }
        pc = next;
    }
    return 0;
}

static int decode_backup(const char *path, const uint8_t *slots) {
    uint8_t file[MAX_FILE_SIZE], output[MAX_FILE_SIZE];
    FILE *input = fopen(path, "rb");
    long file_size;
    size_t instruction_count, decode_count, payload_length;
    size_t code_offset = HEADER_SIZE, decode_offset, payload_offset;
    uint32_t state;

    if (input == NULL) return 0;
    if (fseek(input, 0, SEEK_END) != 0 || (file_size = ftell(input)) < HEADER_SIZE ||
        file_size > MAX_FILE_SIZE || fseek(input, 0, SEEK_SET) != 0) {
        fclose(input);
        return 0;
    }
    if (fread(file, 1, (size_t)file_size, input) != (size_t)file_size) {
        fclose(input);
        return 0;
    }
    fclose(input);

    if (memcmp(file, "TCAP", 4) != 0 || file[4] != 2 || file[7] != 0xC3) return 0;
    instruction_count = file[5];
    decode_count = file[6];
    payload_length = (size_t)file[8] | ((size_t)file[9] << 8);
    decode_offset = code_offset + instruction_count * VALIDATOR_INSTRUCTION_SIZE;
    payload_offset = decode_offset + decode_count * 2;
    if (instruction_count == 0 || decode_count == 0 || decode_count > MAX_DECODE_OPS ||
        payload_length == 0 || payload_offset + payload_length != (size_t)file_size) {
        return 0;
    }
    if (!run_validator(file + code_offset, instruction_count, slots, &state)) return 0;

    for (size_t i = 0; i < payload_length; i++) {
        uint8_t cipher = file[payload_offset + i];
        uint32_t index_mix = (uint32_t)slots[i & 3U] ^ ((uint32_t)i * UINT32_C(0x9E3779B9));
        state = rol32(state + index_mix, (unsigned)(i % 11U) + 5U);
        uint32_t byte_state = state;
        uint8_t value = cipher;

        for (size_t pc = 0; pc < decode_count; pc++) {
            uint8_t op = file[decode_offset + 2 * pc];
            uint8_t operand = file[decode_offset + 2 * pc + 1];
            uint8_t state_byte = (uint8_t)(byte_state >> (8U * (operand & 3U)));
            switch (op) {
                case 0x41: /* XOR with an input slot */
                    if (operand >= 4) return 0;
                    value ^= slots[operand];
                    break;
                case 0x52: /* ADD immediate */
                    value = (uint8_t)(value + operand);
                    break;
                case 0x63: /* ROL byte */
                    value = rol8(value, operand);
                    break;
                case 0x74: /* XOR with a selected state byte */
                    value ^= state_byte;
                    break;
                case 0x85: /* SUB immediate */
                    value = (uint8_t)(value - operand);
                    break;
                case 0x96: /* ADD a selected state byte */
                    value = (uint8_t)(value + state_byte);
                    break;
                case 0xA7: /* XOR with an index-derived byte */
                    value ^= (uint8_t)((uint32_t)i * operand);
                    break;
                default:
                    return 0;
            }
        }
        output[i] = value;
        state = rol32(state ^ ((uint32_t)value + (uint32_t)i * UINT32_C(0x45D9F3B)), 7);
        state += (uint32_t)cipher + UINT32_C(0xA341316C);
    }

    if (fwrite(output, 1, payload_length, stdout) != payload_length) return 0;
    putchar('\n');
    return 1;
}

int main(int argc, char **argv) {
    uint8_t slots[4];

    if (argc != 6) {
        fprintf(stderr, "Usage: %s <slot-1> <slot-2> <slot-3> <slot-4> <backup>\n", argv[0]);
        return 2;
    }
    for (size_t i = 0; i < 4; i++) {
        if (!parse_slot(argv[i + 1], &slots[i])) {
            fprintf(stderr, "The clock face is unreadable.\n");
            return 1;
        }
    }
    if (!decode_backup(argv[5], slots)) {
        fprintf(stderr, "Backup index is damaged; try a different copy.\n");
        return 1;
    }
    return 0;
}
