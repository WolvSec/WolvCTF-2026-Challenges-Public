1. The error messages are intentionally vague. Trace the path from argument parsing into the backup reader.
2. The backup has two programs: a fixed-width validator and a per-byte decoder. Start with the seven-byte validator instructions.
3. The data decoder carries a 32-bit state from one byte to the next. Preserve the order of every update when emulating it.
