import os, struct, fcntl, libnsm
RNDADDENTROPY = 0x40085203

SIZE = 512

fd = libnsm.nsm_lib_init()
data = libnsm.nsm_get_random(fd, SIZE)
libnsm.nsm_lib_exit(fd)

entropy = struct.pack('ii', len(data)*8, len(data)) + data
fcntl.ioctl(os.open("/dev/random", os.O_RDWR), RNDADDENTROPY, entropy)

print("Done initializing /dev/random with entropy from a secure source")

