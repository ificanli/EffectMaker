import bpy
import math
import sys
from mathutils import Vector


def main() -> None:
    arguments = sys.argv[sys.argv.index("--") + 1:]
    if len(arguments) not in (1, 2, 3, 4, 5):
        raise SystemExit("expected an OBJ output path plus optional bezier, sweep, mirror_x, bi_taper, and support flags")

    output_path = arguments[0]
    flags = set(arguments[1:])
    unknown_flags = flags - {"bezier", "sweep", "mirror_x", "bi_taper", "support"}
    if unknown_flags:
        raise SystemExit(f"unsupported flags: {sorted(unknown_flags)}")
    mirror_x = "mirror_x" in flags
    bezier = "bezier" in flags
    sweep = "sweep" in flags
    bi_taper = "bi_taper" in flags
    support = "support" in flags
    if bezier and sweep:
        raise SystemExit("bezier and sweep are mutually exclusive")
    if bi_taper and not bezier:
        raise SystemExit("bi_taper requires bezier")
    if support and not bezier:
        raise SystemExit("support requires bezier")
    if support and bi_taper:
        raise SystemExit("support and bi_taper are mutually exclusive")
    bpy.ops.wm.read_factory_settings(use_empty=True)

    vertices = []
    faces = []
    segment_count = 56 if (sweep or bezier) else 40
    start_angle = math.radians(220.0 if sweep else 195.0)
    end_angle = math.radians(35.0 if sweep else -15.0)
    center_y = 0.0 if sweep else -0.05
    if support:
        bezier_start = Vector((1.48, 0.0, -0.34))
        bezier_control = Vector((0.32, 0.0, -1.20))
        bezier_end = Vector((-1.30, 0.0, -0.08))
    else:
        bezier_start = Vector((1.55, 0.0, -0.58))
        bezier_control = Vector((0.25, 0.0, 1.62))
        bezier_end = Vector((-1.45, 0.0, 0.16))

    for index in range(segment_count + 1):
        progress = index / segment_count
        if bezier:
            inverse_progress = 1.0 - progress
            center = (
                inverse_progress * inverse_progress * bezier_start
                + 2.0 * inverse_progress * progress * bezier_control
                + progress * progress * bezier_end
            )
            tangent = (
                2.0 * inverse_progress * (bezier_control - bezier_start)
                + 2.0 * progress * (bezier_end - bezier_control)
            ).normalized()
            radial = Vector((-tangent.z, 0.0, tangent.x))
            if support:
                center += radial * (0.10 + 0.045 * math.sin(math.pi * progress))
                half_width = (
                    0.004
                    + 0.058 * (math.sin(math.pi * progress) ** 0.84)
                    + 0.016 * progress
                )
            elif bi_taper:
                half_width = (
                    0.006
                    + 0.17 * (math.sin(math.pi * progress) ** 0.72)
                    + 0.012 * progress
                )
            else:
                half_width = (
                    0.012
                    + 0.145 * (math.sin(math.pi * progress) ** 0.68)
                    + 0.075 * progress
                )
        else:
            angle = start_angle + (end_angle - start_angle) * progress
            radius = (1.68 if sweep else 2.02) + 0.08 * math.sin(math.pi * progress)
            radial = Vector((math.cos(angle), 0.0, math.sin(angle)))
            center = Vector((radius * radial.x, 0.0, center_y + radius * radial.z))
            if sweep:
                half_width = (
                    0.008
                    + 0.145 * (math.sin(math.pi * progress) ** 0.72)
                    + 0.055 * progress
                )
            else:
                half_width = (
                    0.015
                    + 0.205 * (math.sin(math.pi * progress) ** 0.68)
                    + 0.065 * progress
                )
        if mirror_x:
            center.x *= -1.0
            radial.x *= -1.0
        vertices.extend((tuple(center - radial * half_width), tuple(center + radial * half_width)))

    for index in range(segment_count):
        if sweep:
            faces.append((2 * index + 1, 2 * index + 3, 2 * index + 2, 2 * index))
        else:
            faces.append((2 * index, 2 * index + 2, 2 * index + 3, 2 * index + 1))

    if support:
        mesh_name = "SlashArc_Support_Derived"
    elif bi_taper:
        mesh_name = "SlashArc_BiTaper_Derived"
    else:
        mesh_name = "SlashArc_Tapered_Derived"
    mesh = bpy.data.meshes.new(mesh_name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            progress = (vertex_index // 2) / segment_count
            edge_index = vertex_index % 2
            uv_layer.data[loop_index].uv = (1.0 - progress, edge_index)

    mesh_object = bpy.data.objects.new(mesh_name, mesh)
    bpy.context.collection.objects.link(mesh_object)
    bpy.context.view_layer.objects.active = mesh_object
    mesh_object.select_set(True)
    bpy.ops.wm.obj_export(
        filepath=output_path,
        export_materials=False,
        export_uv=True,
        export_normals=True,
        export_selected_objects=True,
    )
    print(
        "DERIVED_MESH",
        output_path,
        "vertices",
        len(vertices),
        "faces",
        len(faces),
        "dimensions",
        tuple(round(value, 4) for value in mesh_object.dimensions),
    )


if __name__ == "__main__":
    main()
