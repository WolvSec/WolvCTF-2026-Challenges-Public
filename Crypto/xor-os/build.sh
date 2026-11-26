docker build . -t xor-os:1.0
docker create --name xor-os-builder xor-os:1.0
docker cp xor-os-builder:/chal/dist/chal.bin .

tar -czf dis.tar.gz chal.bin
