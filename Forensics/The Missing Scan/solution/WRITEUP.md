# The Missing Scan — solution

Extract `card.img` from `dis.tar.gz`. It is a FAT12 disk image. List its deleted entries with `fls -d card.img` (or a graphical disk-forensics tool). The deleted entry is `_CAN0003.PNG`.

Use the inode number printed by `fls` to recover it:

```sh
icat -r card.img <inode> > recovered.png
```

Open `recovered.png`. The scan visibly contains `wctf{d3l3t3d_scan_7f2a91}`. The file occupies one cluster, so recovering it does not depend on guessing a deleted FAT chain or carving across fragmented data.
