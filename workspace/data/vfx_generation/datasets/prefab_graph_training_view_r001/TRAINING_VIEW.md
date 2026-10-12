# prefab_graph_training_view_r001

This immutable view is derived from `prefab_graph_full_r002` without changing the source files.

Examples sharing a parameter-agnostic structure sequence or a component-topology sequence are assigned to one `structure_cluster_id`. Train/validation/test are split by that cluster ID, so numeric, color, and closely related topology variants cannot cross the split boundary.

The vocabulary is fit from the train split only. No aesthetic labels, human preference labels, or Prompt quality labels are included. This view is for technical PrefabGraph structure learning and still requires Grammar constraints, AssetPlan routing, Unity compilation, runtime capture, and visual verification.
