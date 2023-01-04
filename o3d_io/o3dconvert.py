# ==============================================================================
#  Copyright (c) 2022 Thomas Mathieson.
# ==============================================================================

import struct
import math


def log(*args):
    print("[O3DConvert]", *args)


# Try to import o3d cryptography module (not available in public plugin release)
try:
    from .o3d_crypto import init_rand, decrypt_vert, encrypt_vert
except ImportError:
    log("[WARNING] o3d_crypto.py could not be loaded! O3D encryption and decryption will not work correctly.")


    def init_rand(encryption_header, alt_encryption_seed, version):
        return 0


    def decrypt_vert(vert, encryption_header, alt_encryption_seed, prev_seed, prev_vpos_seed, n_verts):
        return vert, 0, 0


    def encrypt_vert(vert, encryption_header, alt_encryption_seed, prev_seed, prev_vpos_seed, n_verts):
        return vert, 0, 0


# Takes an o3d vertex and returns (((pos), (nrm), (uv)), bewOffset)
def import_vertex(buff, offset):
    v = struct.unpack_from("<ffffffff", buff, offset=offset)  # xp,yp,zp,xn,yn,zn,u,v
    return [[list(v[0:3]), list(v[3:6]), list(v[6:8])], offset + 8 * 4]


# Takes an o3d triangle struct and returns ((indices, matIndex), newOffset)
def import_triangle(buff, offset, long_triangle_indices, invert_normals=False):
    if long_triangle_indices:
        t = struct.unpack_from("<IIIH", buff, offset=offset)
        offset += 4 * 3 + 2
    else:
        t = struct.unpack_from("<HHHH", buff, offset=offset)
        offset += 2 * 4

    if invert_normals:
        return (t[0:3], t[3]), offset
    else:
        return (t[0:3][::-1], t[3]), offset


# Takes an o3d material struct and returns ((diffuse, specular, specularity, texture_name), newOffset); texture_name
# is set to None if one isn't specified in the file
def import_material(buff, offset):
    m = struct.unpack_from("<fffffffffffB", buff, offset=offset)
    offset += 11 * 4
    # Extract texture path length
    path_len = m[-1] + 1  # Path length
    m_name = None
    if path_len + 1 > 0:
        try:
            m_name = struct.unpack_from("<{0}p".format(str(path_len)), buff, offset=offset)[0].decode("cp1252")
        except:
            m_name = ""
        offset += path_len
    return (m[0:4], m[4:7], m[10], m_name), offset


# Takes an o3d bone struct and returns ((name, weights), newOffset)
def import_bone(buff, offset, long_triangle_indices):
    h = struct.unpack_from("<B", buff, offset=offset)  # Name length
    b_name = struct.unpack_from("<{0}p".format(str(h[0] + 1)), buff, offset=offset)[0].decode("cp1252",
                                                                                              errors="backslashreplace")
    offset += h[0] + 1

    n_weights = struct.unpack_from("<H", buff, offset=offset)
    offset += 2
    weights = []
    for w in range(n_weights[0]):
        weights.append(struct.unpack_from("<If" if long_triangle_indices else "<Hf", buff, offset=offset))
        offset += 8 if long_triangle_indices else 6

    return (b_name, weights), offset


# Imports a list of o3d vertices and returns (vertices, newOffset)
def import_vertex_list(buff, offset, l_header, encrypted, alt_encryption_seed, encryption_header, version):
    if l_header:
        header = struct.unpack_from("<I", buff, offset=offset)[0]
        offset += 4
    else:
        header = struct.unpack_from("<H", buff, offset=offset)[0]
        offset += 2

    verts = []
    prev_vpos_seed = 0
    prev_seed = init_rand(encryption_header, alt_encryption_seed, version)
    for v in range(header):
        nv = import_vertex(buff, offset)
        if encrypted:
            nv[0], prev_seed, prev_vpos_seed = decrypt_vert(nv[0], encryption_header, alt_encryption_seed, prev_seed,
                                                            prev_vpos_seed, header)

        verts.append(nv[0])
        offset = nv[1]

    return verts, offset


# Imports a list of o3d triangles and returns (triangles, newOffset)
def import_triangle_list(buff, offset, l_header, long_triangle_indices):
    if l_header:
        header = struct.unpack_from("<I", buff, offset=offset)[0]
        offset += 4
    else:
        header = struct.unpack_from("<H", buff, offset=offset)[0]
        offset += 2

    tris = []
    for t in range(header):
        nt = import_triangle(buff, offset, long_triangle_indices)
        tris.append(nt[0])
        offset = nt[1]

    return tris, offset


# Imports a list of o3d materials and returns (materials, newOffset)
def import_material_list(buff, offset, l_header):
    # IDK why but materials don't get the long header...
    header = struct.unpack_from("<H", buff, offset=offset)[0]
    offset += 2

    mats = []
    for m in range(header):
        nm = import_material(buff, offset)
        mats.append(nm[0])
        offset = nm[1]

    return mats, offset


# Imports a list of o3d bones and returns (bones, newOffset)
def import_bone_list(buff, offset, l_header, long_triangle_indices):
    if l_header:
        header = struct.unpack_from("<I", buff, offset=offset)[0]
        offset += 4
    else:
        header = struct.unpack_from("<H", buff, offset=offset)[0]
        offset += 2

    bones = []
    for b in range(header):
        nb = import_bone(buff, offset, long_triangle_indices)
        bones.append(nb[0])
        offset = nb[1]

    return bones, offset


# Imports an o3d transform struct and returns (transform, newOffset)
def import_transform(buff, offset):
    m = struct.unpack_from("<ffffffffffffffff", buff, offset=offset)
    offset += 16 * 4
    return (
               (m[0], m[4], m[8], m[12]),
               (m[1], m[5], m[9], m[13]),
               (m[2], m[6], m[10], m[14]),
               (m[3], m[7], m[11], m[15])
           ), offset


def import_o3d(packed_bytes):
    header = struct.unpack_from("<BBB", packed_bytes, offset=0)
    off = 3
    l_header = False
    encrypted = False
    bonus_header = [0, 0]
    if header[0:2] == (0x84, 0x19):
        if header[2] > 3:
            # Long header variant, sometimes encrypted
            bonus_header = struct.unpack_from("<BI", packed_bytes, offset=off)
            # log("Extended header options: long_triangle_indices={0}; alt_encryption_seed={1}".format(
            #    bonus_header[0] & 1 == 1, bonus_header[0] & 2 == 2))
            if bonus_header[1] != 0xffffffff:
                encrypted = True
                # log("Encrypted file detected!")
            off += 5
            l_header = True
    else:
        log(
            "WARNING: O3D file has an unsupported header (found={0}; expected=(0x84,0x19,0x01). File might not import "
            "correctly...".format(
                list(map(hex, header))))

    vertex_list = []
    triangle_list = []
    material_list = []
    bone_list = []
    transform = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    while off < len(packed_bytes) - 1:
        section = struct.unpack_from("<B", packed_bytes, offset=off)[0]
        off += 1
        if section == 0x17:
            vertex_list, off = import_vertex_list(packed_bytes, off, l_header, encrypted, bonus_header[0] & 2 == 2,
                                                  bonus_header[1], header[2])
            # log("Loaded {0} vertices!".format(len(vertex_list)))
        elif section == 0x49:
            triangle_list, off = import_triangle_list(packed_bytes, off, l_header, bonus_header[0] & 1 == 1)
            # log("Loaded {0} triangles!".format(len(triangle_list)))
        elif section == 0x26:
            material_list, off = import_material_list(packed_bytes, off, l_header)
            # log("Loaded {0} materials!".format(len(material_list)))
        elif section == 0x54:
            bone_list, off = import_bone_list(packed_bytes, off, l_header, bonus_header[0] & 1 == 1)
            # log("Loaded {0} bones!".format(len(bone_list)))
        elif section == 0x79:
            transform, off = import_transform(packed_bytes, off)
        else:
            log("Unexpected section header encountered in o3d file: " + hex(section) + " at: " + hex(off))
            break

        # triangle_list, off = import_triangle_list(packed_bytes, off, l_header, bonus_header[0])
        # # log("Loaded {0} triangles!".format(len(triangle_list)))
        # material_list, off = import_material_list(packed_bytes, off, l_header)
        # # log("Loaded {0} materials!".format(len(material_list)))
        # bone_list, off = import_bone_list(packed_bytes, off, l_header)
        # # log("Loaded {0} bones!".format(len(bone_list)))
        # transform, off = import_transform(packed_bytes, off)

    return header, vertex_list, triangle_list, material_list, bone_list, transform, encrypted


def export_vertex(write, vertex):
    """
    Exports an O3D vertex
    :param write: the file writer function
    :param vertex: the vertex to export as a tuple in the form: xp, yp, zp, xn, yn, zn, u, v
    """
    write("<ffffffff", *vertex)  # xp,yp,zp,xn,yn,zn,u,v


def export_triangle(write, triangle, long_triangle_indices, invert_normals=False):
    """
    Exports an O3D triangle
    :param write: the file writer function
    :param triangle: the triangle to export as a tuple in the form: a, b, c, mat_index
    :param long_triangle_indices: whether long triangle indices (32 bit) are used
    :param invert_normals: whether to invert the triangle winding
    """
    write("<IIIH" if long_triangle_indices else "<HHHH",
          *(triangle[0:3][::-1] if invert_normals else triangle[0:3]), triangle[3])


def export_material(write, material):
    """
    Exports an O3D material
    :param write: the file writer function
    :param material: the material to export as a tuple in the form:
    (diffuse_r, diffuse_g, diffuse_b, diffuse_a, specular_r, specular_g, specular_b, emission_r, emission_g, emission_b,
    specular_power, texture_name)
    """
    write("<fffffffffff", *material[:-1])
    write("<{0}p".format(len(material[-1]) + 1), material[-1].encode("cp1252"))


def export_bone(write, bone, long_triangle_indices):
    write("<B", len(bone[0]))
    write("<{0}p".format(len(bone[0])), bone[0].encode("cp1252"))

    write("<H", len(bone[1]))
    for w in bone[1]:
        write("<If" if long_triangle_indices else "<Hf", *w)


def export_vertex_list(write, vertex_list, encrypted, encryption_key, long_header, alt_encryption_seed, version):
    """
    Exports a list of vertices to an O3D file
    :param write: the file writer function
    :param vertex_list: the vertex list to export
    :param encrypted: whether the vertex list should be encrypted
    :param encryption_key: the encryption key to encrypt with
    :param long_header: whether the file uses long headers
    :param alt_encryption_seed: whether the alternative encryption seed is used
    :param version: the o3d file version
    """
    write("<B", 0x17)
    if long_header:
        write("<I", len(vertex_list))
    else:
        write("<H", len(vertex_list))

    prev_vpos_seed = 0
    prev_seed = init_rand(encryption_key, alt_encryption_seed, version)
    for v in vertex_list:
        if encrypted:
            v, prev_seed, prev_vpos_seed = encrypt_vert(v, encryption_key, alt_encryption_seed, prev_seed,
                                                        prev_vpos_seed, version)
        export_vertex(write, v)


def export_triangle_list(write, triangle_list, long_triangle_indices, long_header, invert_triangle_winding=False):
    """
    Exports a list of triangles to an O3D file
    :param write: the file writer function
    :param triangle_list: the list of triangles to export
    :param long_triangle_indices: whether the triangle indices are 32 bit
    :param long_header: whether the file uses long headers
    """
    write("<B", 0x49)
    if long_header:
        write("<I", len(triangle_list))
    else:
        write("<H", len(triangle_list))

    for t in triangle_list:
        export_triangle(write, t, long_triangle_indices, invert_triangle_winding)


def export_material_list(write, material_list, long_header):
    if len(material_list) == 0:
        return

    write("<B", 0x26)
    # No long headers for materials
    # if long_header:
    #     write("<I", len(material_list))
    # else:
    write("<H", len(material_list))

    for m in material_list:
        export_material(write, m)


def export_bone_list(write, bone_list, long_header, long_triangle_indices):
    if len(bone_list) == 0:
        return

    write("<B", 0x54)
    if long_header:
        write("<I", 0)
    else:
        write("<H", 0)

    for bone in bone_list:
        export_bone(write, bone, long_triangle_indices)


def export_transform(write, transform):
    # For now this just exports an identity matrix
    # TODO: Export correct transform matrix
    if transform is None:
        transform = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)

    write("<B", 0x79)
    m = transform
    write("<ffffffffffffffff", *m)


def export_o3d(file, vertex_list, triangle_list, material_list, bone_list, transform, encrypted=False,
               encryption_key=0xffffffff, version=7, long_triangle_indices=True, alt_encryption_seed=True,
               invert_triangle_winding=False):
    # Convenience function to pack and write bytes
    def write(fmt, *args):
        file.write(struct.pack(fmt, *args))

    # Write header
    write("<BBB", 0x84, 0x19, version)
    long_header = version > 3
    if version > 3:
        # Write extended header
        options_byte = (1 if long_triangle_indices else 0) | (2 if alt_encryption_seed else 0)
        if not encrypted:
            encryption_key = 0xffffffff
        write("<BI", options_byte, encryption_key)

    if version <= 3:
        if long_triangle_indices:
            log("WARNING: O3D files with a version < 3 don't support long triangle "
                "indices, the file will be unreadable")
        if alt_encryption_seed:
            log("WARNING: O3D files with a version < 3 don't support the alt encryption "
                "seed")
        if encrypted:
            log("WARNING: O3D files with a version < 3 don't support encryption, the "
                "file will be unreadable")

    export_vertex_list(write, vertex_list, encrypted, encryption_key, long_header, alt_encryption_seed, version)
    # log("Wrote {0} vertices!".format(len(vertex_list)))
    export_triangle_list(write, triangle_list, long_triangle_indices, long_header, invert_triangle_winding)
    # log("Wrote {0} triangles!".format(len(triangle_list)))
    export_material_list(write, material_list, long_header)
    # log("Wrote {0} materials!".format(len(material_list)))
    export_bone_list(write, bone_list, long_header, long_triangle_indices)
    # log("Wrote {0} bones!".format(len(bone_list)))
    export_transform(write, transform)
