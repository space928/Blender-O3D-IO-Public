# BPP and block sizes for all DXGI formats
# Since dxgi formats are enumerated from 0 onward there is no need for dictionary
# if some formats are not suited for storing the value is going to be set to 0
# Sizes are in BYTES
dxgi_pixel_or_block_size = [
    0,
    16, 16, 16, 16,
    12, 12, 12, 12,
    8, 8, 8, 8, 8, 8,
    8, 8, 8, 8,
    8, 8, 8, 8,
    4, 4, 4, 4,
    4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4,
    4,
    4, 4, 4,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1,
    0,  # DXGI_FORMAT_R1_UNORM ehm >.< ( TODO )
    4, 4, 4,
    8, 8, 8,  # BC1
    16, 16, 16,  # BC2
    16, 16, 16,  # BC3
    8, 8, 8,  # BC4
    16, 16, 16,  # BC5
    2, 2,
    4, 4, 4, 4, 4, 4, 4,
    16, 16, 16,  # BC6
    16, 16, 16,  # BC7
    # TODO Complete the rest
]

dxgi_compressed_formats = [
    70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84,
    94, 95, 96, 97, 98, 99
]


class DwFlags:
    ALPHAPIXELS = 0x1
    ALPHA = 0x2
    FOURCC = 0x4
    RGB = 0x40
    YUV = 0x200
    LUMINANCE = 0x20000
    RGBA = RGB | ALPHA
    RGB_ALPHAPIXELS = RGB | ALPHA


four_cc_to_dxgi = {
    int.from_bytes(bytearray(b"DXT1"), byteorder="little", signed=False): 71,
    int.from_bytes(bytearray(b"DXT2"), byteorder="little", signed=False): 74,
    int.from_bytes(bytearray(b"DXT3"), byteorder="little", signed=False): 74,
    int.from_bytes(bytearray(b"DXT4"), byteorder="little", signed=False): 77,
    int.from_bytes(bytearray(b"DXT5"), byteorder="little", signed=False): 77,
}

format_to_dxgi = {
    (DwFlags.RGBA, 32, 0xff, 0xff00, 0xff0000, 0xff000000): 28,
    (DwFlags.RGBA, 32, 0xffff, 0xffff0000, 0, 0): 35,
    (DwFlags.RGBA, 32, 0x3ff, 0xffc00, 0x3ff00000, 0): 24,
    (DwFlags.RGB, 32, 0xffff, 0xff0000, 0, 0): 35,
    (DwFlags.RGBA, 16, 0x7c00, 0x3e0, 0x1f, 0x8000): 86,
    (DwFlags.RGB, 16, 0xf800, 0x7e0, 0x1f, 0): 85,
    (DwFlags.ALPHA, 8, 0, 0, 0, 0xff): 65,
    (DwFlags.RGBA, 32, 0xff0000, 0xff00, 0xff, 0xff000000): -1,
    (DwFlags.RGB, 32, 0xff0000, 0xff00, 0xff, 0): -1,
    (DwFlags.RGB, 32, 0xff, 0xff00, 0xff0000, 0): -1,
    (DwFlags.RGBA, 32, 0x3ff00000, 0xffc00, 0x3ff, 0xc0000000): -1,
    (DwFlags.RGB, 24, 0xff0000, 0xff00, 0xff, 0): -1,
    (DwFlags.RGB, 16, 0x7c00, 0x3e0, 0x1f, 0): -1,
    (DwFlags.RGBA, 16, 0xf00, 0xf0, 0xf, 0xf000): -1,
    (DwFlags.RGB, 16, 0xf00, 0xf0, 0xf, 0): -1,
    (DwFlags.RGBA, 16, 0xe0, 0x1c, 0x3, 0xff00): -1,
    (DwFlags.LUMINANCE, 16, 0xff, 0, 0, 0xff00): -1,
    (DwFlags.LUMINANCE, 16, 0xffff, 0, 0, 0): -1,
    (DwFlags.LUMINANCE, 8, 0xff, 0, 0, 0): -1,
    (DwFlags.LUMINANCE, 8, 0xf, 0, 0, 0xf0): -1,
    (DwFlags.RGB_ALPHAPIXELS, 32, 0xff0000, 0xff00, 0xff, 0xff000000): 87,  # DXGI_FORMAT_B8G8R8A8_UNORM
}
