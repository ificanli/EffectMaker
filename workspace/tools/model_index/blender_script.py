SCRIPT = r'''
import bpy, json, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
asset, preview_root, asset_id = argv[0], argv[1], argv[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
if asset.lower().endswith(".fbx"):
    bpy.ops.import_scene.fbx(filepath=asset)
elif asset.lower().endswith(".obj"):
    bpy.ops.wm.obj_import(filepath=asset)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
verts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
polygons = [p for o in meshes for p in o.data.polygons]
triangles = sum(max(0, len(p.vertices) - 2) for p in polygons)
if verts:
    minimum = [min(v[i] for v in verts) for i in range(3)]
    maximum = [max(v[i] for v in verts) for i in range(3)]
else:
    minimum = maximum = [0.0, 0.0, 0.0]
target = Vector(((minimum[0]+maximum[0])/2, (minimum[1]+maximum[1])/2, (minimum[2]+maximum[2])/2))
extents = [maximum[i]-minimum[i] for i in range(3)]
size = sum(value * value for value in extents) ** 0.5 if verts else 1.0
uv_layers = sum(len(o.data.uv_layers) for o in meshes)
colors = any(bool(getattr(o.data, "color_attributes", [])) for o in meshes)
normals = any(len(o.data.vertex_normals) > 0 for o in meshes)
materials = sum(len(o.material_slots) for o in meshes)
animations = len(bpy.data.actions)
preview_dir = preview_root
os.makedirs(preview_dir, exist_ok=True)
previews = {}
if meshes:
    for name, direction in (("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0))), ("perspective", Vector((1, -1, 0.75)))):
        distance = max(size * 2.2, 1.0)
        camera = bpy.data.cameras.new(name)
        camera_obj = bpy.data.objects.new(name, camera)
        bpy.context.collection.objects.link(camera_obj)
        camera_obj.location = target + direction.normalized() * distance
        camera_obj.rotation_euler = (target - camera_obj.location).to_track_quat('-Z', 'Y').to_euler()
        camera.type = 'ORTHO'
        camera.ortho_scale = max(size * 1.25, 1.0)
        bpy.context.scene.camera = camera_obj
        bpy.context.scene.render.resolution_x = 256
        bpy.context.scene.render.resolution_y = 256
        bpy.context.scene.render.resolution_percentage = 100
        path = os.path.join(preview_dir, asset_id + "-" + name + ".png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        previews[name] = path
        bpy.data.objects.remove(camera_obj, do_unlink=True)
print("MODEL_INDEX_RESULT:" + json.dumps({"vertex_count": len(verts), "polygon_count": len(polygons), "triangle_count": triangles, "bounds": {"min": minimum, "max": maximum}, "uv_layer_count": uv_layers, "has_vertex_colors": colors, "has_normals": normals, "material_slot_count": materials, "animation_count": animations, "previews": previews}))
'''
