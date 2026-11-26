The secret message is ROT13, and the rotated text is stored in the poster. Read every pixel left to right, top to bottom, and take the least significant bit of blue. Pack those bits into bytes, most significant bit first.

ROT13 rotates letters by 13 places and leaves digits, underscores, and braces alone. Rotating the extracted text back gives:

wctf{r0t13_1n_th3_blu3}

solution/solve.py does this. To change the flag, edit flag.txt and run python challenge/generate.py.
