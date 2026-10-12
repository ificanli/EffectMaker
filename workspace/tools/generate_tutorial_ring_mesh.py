import argparse
import math
import sys

import bpy


def build_ring(output_path: str, outer: bool) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    segments = 128
    width_segments = 6
    if outer:
        start_degrees = -122.0
        end_degrees = 104.0
        radius = 0.49
        width = 0.058
        name = "TutorialOuter_CRing"
    else:
        start_degrees = -137.0
        end_degrees = 136.0
        radius = 0.43
        width = 0.098
        name = "TutorialCore_CRing"

    vertices = []
    faces = []
    for segment in range(segments + 1):
        progress = segment / segments
        angle = math.radians(start_degrees + (end_degrees - start_degrees) * progress)
        radial_x = math.cos(angle)
        radial_y = math.sin(angle)
        center_x = radius * radial_x
        center_y = radius * radial_y
        taper = 0.10 + 0.90 * (math.sin(math.pi * progress) ** 0.68)
        if outer:
            taper *= 0.94 + 0.06 * math.sin(math.pi * progress * 2.0)
        local_width = width * taper
        for across in range(width_segments + 1):
            across_progress = across / width_segments
            signed_width = (across_progress - 0.5) * 2.0 * local_width
            vertices.append(
                (
                    center_x + radial_x * signed_width,
                    0.0,
                    center_y + radial_y * signed_width,
                )
            )

    row_width = width_segments + 1
    for segment in range(segments):
        for across in range(width_segments):
            a = segment * row_width + across
            b = a + 1
            c = a + row_width + 1
            d = a + row_width
            faces.append((a, b, c, d))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            segment = vertex_index // row_width
            across = vertex_index % row_width
            uv_layer.data[loop_index].uv = (
                segment / segments,
                across / width_segments,
            )

    mesh_object = bpy.data.objects.new(name, mesh)
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
        "TUTORIAL_RING_MESH",
        output_path,
        "outer",
        outer,
        "vertices",
        len(vertices),
        "faces",
        len(faces),
    )


def main() -> None:
    arguments = sys.argv[sys.argv.index("--") + 1 :]
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--outer", action="store_true")
    args = parser.parse_args(arguments)
    build_ring(args.output, args.outer)


if __name__ == "__main__":
    main()
