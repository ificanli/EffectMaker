#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

public class YOYOShaderGUI : ShaderGUI
{
    // ===================== 自定义 Foldout 样式（参考PandaShader）=====================
    static bool CustomFoldout(bool display, string title)
    {
        var style = new GUIStyle("ShurikenModuleTitle");
        style.font = new GUIStyle(EditorStyles.boldLabel).font;
        style.border = new RectOffset(15, 7, 4, 4);
        style.fixedHeight = 22;
        style.contentOffset = new Vector2(20f, -2f);
        style.fontSize = 11;
        style.normal.textColor = new Color(0.7f, 0.8f, 0.9f);

        var rect = GUILayoutUtility.GetRect(16f, 25f, style);
        GUI.Box(rect, title, style);

        var e = Event.current;
        var toggleRect = new Rect(rect.x + 4f, rect.y + 2f, 13f, 13f);
        if (e.type == EventType.Repaint)
        {
            EditorStyles.foldout.Draw(toggleRect, false, false, display, false);
        }

        if (e.type == EventType.MouseDown && rect.Contains(e.mousePosition))
        {
            display = !display;
            e.Use();
        }

        return display;
    }

    // ===================== 折叠状态 =====================
    static bool foldRender      = true;
    static bool foldMain        = true;
    static bool foldSecondColor = false;
    static bool foldMask        = false;
    static bool foldDistort     = false;
    static bool foldDissolve    = false;
    static bool foldFresnel     = false;
    static bool foldCustom      = true;

    static readonly string[] BlendNames     = { "AlphaBlend（透明混合）", "Add（叠加）", "Opaque（不透明）" };
    static readonly int[]    BlendSrcValues = { 5, 5, 1 };
    static readonly int[]    BlendDstValues = { 10, 1, 0 };

    static readonly string[] ZTestNames  = { "Default（默认深度）", "Always（始终显示）" };
    static readonly int[]    ZTestValues = { 4, 8 };

    static readonly string[] CullNames  = { "Off（双面显示）", "On（剔除背面）" };
    static readonly int[]    CullValues = { 0, 2 };

    static readonly string[] RenderQueueNames  = { "Background (1000)", "Geometry (2000)", "AlphaTest (2450)", "Transparent (3000)", "Overlay (4000)" };
    static readonly int[]    RenderQueueValues = { 1000, 2000, 2450, 3000, 4000 };

    public override void OnGUI(MaterialEditor me, MaterialProperty[] props)
    {
        Material mat = me.target as Material;

        GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel);
        titleStyle.fontSize = 14;
        titleStyle.normal.textColor = new Color(0.7f, 0.8f, 0.9f);
        titleStyle.alignment = TextAnchor.MiddleCenter;
        EditorGUILayout.Space(4);
        GUILayout.Label("✦ YOYO Shader 控制面板  v2.4", titleStyle);
        EditorGUILayout.Space(2);

        // ==================== 渲染设置 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldRender = CustomFoldout(foldRender, "渲染设置");
        if (foldRender)
        {
            EditorGUI.indentLevel++;
            DrawBlendPopup(me, props);
            GUILayout.Space(5);
            DrawZTestPopup(me, props);
            GUILayout.Space(5);
            DrawCullPopup(me, props);
            GUILayout.Space(5);
            DrawRenderQueuePopup(me);
            GUILayout.Space(5);
            SafeDraw(me, props, "_FClip", "启用透明剪裁（Alpha Clip）");
            if (IsEnabled(props, "_FClip"))
            {
                GUILayout.Space(2);
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                SafeDraw(me, props, "_Cutoff", "剪裁阈值");
                EditorGUILayout.EndVertical();
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== 主贴图 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldMain = CustomFoldout(foldMain, "主贴图设置");
        if (foldMain)
        {
            EditorGUI.indentLevel++;
            
            MaterialProperty mainTex = FindProperty("_MainTex", props, false);
            if (mainTex != null)
            {
                me.TexturePropertySingleLine(new GUIContent("主贴图"), mainTex, 
                    FindProperty("_MainColor", props, false));
                GUILayout.Space(3);

                // ★新增：主贴图拼接模式（Repeat / Clamp）
                SafeDraw(me, props, "_MainTexWrap", "拼接模式（Repeat / Clamp）");
                GUILayout.Space(3);

                SafeDraw(me, props, "_MainUseRChannel", "使用R通道");
                GUILayout.Space(5);

                EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                me.TextureScaleOffsetProperty(mainTex);
                EditorGUILayout.EndVertical();
                GUILayout.Space(5);

                SafeDraw(me, props, "_MainSpeedU",   "U 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_MainSpeedV",   "V 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_MainRotation", "旋转角度");
                GUILayout.Space(5);

                SafeDraw(me, props, "_MainUseCustomData", "使用 CustomData1.XY 控制UV偏移");
                if (IsEnabled(props, "_MainUseCustomData"))
                {
                    EditorGUILayout.HelpBox(
                        "CustomData1.X = U偏移\nCustomData1.Y = V偏移\n开启后速度参数失效。",
                        MessageType.None);
                    GUILayout.Space(3);
                }

                GUILayout.Space(3);
                DrawSeparator();
                GUILayout.Space(3);

                SafeDraw(me, props, "_FMainOverlay", "开启附加叠加贴图");
                if (IsEnabled(props, "_FMainOverlay"))
                {
                    GUILayout.Space(3);
                    EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                    MaterialProperty overlayTex = FindProperty("_MainOverlayTex", props, false);
                    if (overlayTex != null)
                    {
                        me.TexturePropertySingleLine(new GUIContent("附加贴图"), overlayTex,
                            FindProperty("_MainOverlayColor", props, false));
                        GUILayout.Space(3);
                        me.TextureScaleOffsetProperty(overlayTex);
                        GUILayout.Space(5);

                        SafeDraw(me, props, "_MainOverlaySpeedU",   "附加贴图 U 速度");
                        GUILayout.Space(3);
                        SafeDraw(me, props, "_MainOverlaySpeedV",   "附加贴图 V 速度");
                        GUILayout.Space(3);
                        SafeDraw(me, props, "_MainOverlayRotation", "附加贴图旋转角度");
                        GUILayout.Space(3);
                    }
                    SafeDraw(me, props, "_MainOverlayMode",  "叠加模式");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_MainOverlayBlend", "融合系数（0-100）");
                    EditorGUILayout.EndVertical();
                }
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== 第二颜色 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldSecondColor = CustomFoldout(foldSecondColor, "第二颜色设置");
        if (foldSecondColor)
        {
            EditorGUI.indentLevel++;
            SafeDraw(me, props, "_FSecondColor", "开启第二颜色");
            if (IsEnabled(props, "_FSecondColor"))
            {
                GUILayout.Space(3);
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);

                MaterialProperty secondTex = FindProperty("_SecondColorTex", props, false);
                if (secondTex != null)
                {
                    me.TexturePropertySingleLine(new GUIContent("颜色渐变贴图"), secondTex);
                    GUILayout.Space(5);
                    me.TextureScaleOffsetProperty(secondTex);
                    GUILayout.Space(5);
                }
                SafeDraw(me, props, "_SecondColorTint",    "颜色叠加色调（支持HDR）");
                GUILayout.Space(3);
                SafeDraw(me, props, "_SecondColorSpeedU",  "U 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_SecondColorSpeedV",  "V 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_SecondColorRotation","旋转角度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_SecondColorMode",    "叠加模式");
                GUILayout.Space(3);
                SafeDraw(me, props, "_SecondColorBlend",   "与主贴图混合强度（0-100）");

                EditorGUILayout.EndVertical();
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== 遮罩 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldMask = CustomFoldout(foldMask, "遮罩设置");
        if (foldMask)
        {
            EditorGUI.indentLevel++;
            SafeDraw(me, props, "_FMask", "开启遮罩");
            if (IsEnabled(props, "_FMask"))
            {
                GUILayout.Space(3);
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);

                MaterialProperty maskTex = FindProperty("_MaskTex", props, false);
                if (maskTex != null)
                {
                    me.TexturePropertySingleLine(new GUIContent("遮罩贴图"), maskTex);
                    GUILayout.Space(3);

                    // ★新增：遮罩贴图拼接模式（Repeat / Clamp）
                    SafeDraw(me, props, "_MaskWrap", "拼接模式（Repeat / Clamp）");
                    GUILayout.Space(3);

                    SafeDraw(me, props, "_MaskUseRChannel", "使用R通道");
                    GUILayout.Space(5);
                    me.TextureScaleOffsetProperty(maskTex);
                    GUILayout.Space(5);
                }
                SafeDraw(me, props, "_MaskSpeedU",   "U 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_MaskSpeedV",   "V 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_MaskRotation", "旋转角度");
                GUILayout.Space(5);
                SafeDraw(me, props, "_MaskUseCustomData", "使用 CustomData1.ZW 控制UV偏移");
                if (IsEnabled(props, "_MaskUseCustomData"))
                {
                    EditorGUILayout.HelpBox("CustomData1.Z = U偏移\nCustomData1.W = V偏移。", MessageType.None);
                    GUILayout.Space(3);
                }

                DrawSeparator();
                SafeDraw(me, props, "_FMask2", "开启附加遮罩贴图");
                if (IsEnabled(props, "_FMask2"))
                {
                    GUILayout.Space(3);
                    EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                    MaterialProperty maskTex2 = FindProperty("_MaskTex2", props, false);
                    if (maskTex2 != null)
                    {
                        me.TexturePropertySingleLine(new GUIContent("附加遮罩贴图"), maskTex2);
                        GUILayout.Space(3);
                        SafeDraw(me, props, "_MaskTex2UseRChannel", "使用R通道");
                        GUILayout.Space(5);
                        me.TextureScaleOffsetProperty(maskTex2);
                        GUILayout.Space(5);
                    }
                    SafeDraw(me, props, "_MaskTex2SpeedU",   "U 方向速度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_MaskTex2SpeedV",   "V 方向速度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_MaskTex2Rotation", "旋转角度");
                    EditorGUILayout.EndVertical();
                }

                EditorGUILayout.EndVertical();
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== 扭曲 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldDistort = CustomFoldout(foldDistort, "UV扭曲设置");
        if (foldDistort)
        {
            EditorGUI.indentLevel++;
            SafeDraw(me, props, "_FDistort", "开启UV扭曲");
            if (IsEnabled(props, "_FDistort"))
            {
                GUILayout.Space(3);
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);

                MaterialProperty distortTex = FindProperty("_DistortTex", props, false);
                if (distortTex != null)
                {
                    me.TexturePropertySingleLine(new GUIContent("扭曲贴图（RG 双通道）"), distortTex);
                    GUILayout.Space(3);
                    me.TextureScaleOffsetProperty(distortTex);
                    GUILayout.Space(5);
                }
                SafeDraw(me, props, "_DistortStrength", "扭曲强度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DistortSpeedU",   "U 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DistortSpeedV",   "V 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DistortRotation", "旋转角度");
                GUILayout.Space(5);
                SafeDraw(me, props, "_DistortUseCustomData", "使用 CustomData2.XY 控制UV偏移");
                if (IsEnabled(props, "_DistortUseCustomData"))
                {
                    EditorGUILayout.HelpBox("CustomData2.X = U偏移\nCustomData2.Y = V偏移。", MessageType.None);
                    GUILayout.Space(3);
                }

                DrawSeparator();
                SafeDraw(me, props, "_FDistort2", "开启附加扭曲贴图");
                if (IsEnabled(props, "_FDistort2"))
                {
                    GUILayout.Space(3);
                    EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                    MaterialProperty distortTex2 = FindProperty("_DistortTex2", props, false);
                    if (distortTex2 != null)
                    {
                        me.TexturePropertySingleLine(new GUIContent("附加扭曲贴图（RG 双通道）"), distortTex2);
                        GUILayout.Space(5);
                        me.TextureScaleOffsetProperty(distortTex2);
                        GUILayout.Space(5);
                    }
                    SafeDraw(me, props, "_DistortTex2Strength", "附加扭曲强度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_DistortTex2SpeedU",   "U 方向速度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_DistortTex2SpeedV",   "V 方向速度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_DistortTex2Rotation", "旋转角度");
                    EditorGUILayout.EndVertical();
                }

                EditorGUILayout.EndVertical();
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== 溶解 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldDissolve = CustomFoldout(foldDissolve, "溶解设置");
        if (foldDissolve)
        {
            EditorGUI.indentLevel++;
            SafeDraw(me, props, "_FDissolve", "开启溶解");
            if (IsEnabled(props, "_FDissolve"))
            {
                GUILayout.Space(3);
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);

                MaterialProperty dissolveTex = FindProperty("_DissolveTex", props, false);
                if (dissolveTex != null)
                {
                    me.TexturePropertySingleLine(new GUIContent("溶解贴图"), dissolveTex);
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_DissolveUseRChannel", "使用R通道（黑白噪波图请勾选）");
                    GUILayout.Space(5);
                    me.TextureScaleOffsetProperty(dissolveTex);
                    GUILayout.Space(5);
                }
                SafeDraw(me, props, "_DissolveThreshold", "基础阈值（0=完整, 1=消失）");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DissolveSoftness",  "边缘软硬度（越大过渡越柔）");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DissolveSpeedU",    "U 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DissolveSpeedV",    "V 方向速度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DissolveEdgeColor", "边缘发光颜色");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DissolveEdgeWidth", "边缘发光宽度");
                GUILayout.Space(3);
                SafeDraw(me, props, "_DissolveRotation",  "旋转角度");
                GUILayout.Space(5);
                SafeDraw(me, props, "_DissolveUseCustomData", "使用 CustomData2.Z 控制溶解阈值");
                if (IsEnabled(props, "_DissolveUseCustomData"))
                {
                    EditorGUILayout.HelpBox("CustomData2.Z 直接控制每颗粒子的溶解进度。\n基础阈值此时失效。", MessageType.None);
                    GUILayout.Space(3);
                }

                DrawSeparator();
                SafeDraw(me, props, "_FDissolve2", "开启附加溶解贴图");
                if (IsEnabled(props, "_FDissolve2"))
                {
                    GUILayout.Space(3);
                    EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                    MaterialProperty dissolveTex2 = FindProperty("_DissolveTex2", props, false);
                    if (dissolveTex2 != null)
                    {
                        me.TexturePropertySingleLine(new GUIContent("附加溶解贴图（噪波）"), dissolveTex2);
                        GUILayout.Space(5);
                        me.TextureScaleOffsetProperty(dissolveTex2);
                        GUILayout.Space(5);
                    }
                    SafeDraw(me, props, "_DissolveTex2SpeedU",   "U 方向速度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_DissolveTex2SpeedV",   "V 方向速度");
                    GUILayout.Space(3);
                    SafeDraw(me, props, "_DissolveTex2Rotation", "旋转角度");
                    EditorGUILayout.EndVertical();
                }

                EditorGUILayout.EndVertical();
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== 菲涅尔 ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldFresnel = CustomFoldout(foldFresnel, "菲涅尔设置");
        if (foldFresnel)
        {
            EditorGUI.indentLevel++;
            SafeDraw(me, props, "_FFresnel", "开启菲涅尔");
            if (IsEnabled(props, "_FFresnel"))
            {
                GUILayout.Space(3);
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                SafeDraw(me, props, "_FresnelColor",   "菲涅尔颜色（支持HDR）");
                GUILayout.Space(3);
                SafeDraw(me, props, "_FresnelPower",   "强度（越大越锐利）");
                GUILayout.Space(3);
                SafeDraw(me, props, "_FresnelScale",   "范围（越大覆盖越广）");
                GUILayout.Space(3);
                SafeDraw(me, props, "_FresnelReverse", "反转（开启=内发光，关闭=边缘发光）");
                EditorGUILayout.EndVertical();
            }
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();

        // ==================== Custom Data ====================
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        foldCustom = CustomFoldout(foldCustom, "Custom Data 通道总览");
        if (foldCustom)
        {
            EditorGUI.indentLevel++;
            SafeDraw(me, props, "_AlphaUseCustomData", "使用 CustomData2.W 控制全局透明度");
            GUILayout.Space(5);
            EditorGUILayout.HelpBox(
                "【通道对照表】\n\n" +
                "CustomData1.X  →  主贴图 U 偏移\n" +
                "CustomData1.Y  →  主贴图 V 偏移\n" +
                "CustomData1.Z  →  遮罩贴图 U 偏移\n" +
                "CustomData1.W  →  遮罩贴图 V 偏移\n" +
                "CustomData2.X  →  扭曲贴图 U 偏移\n" +
                "CustomData2.Y  →  扭曲贴图 V 偏移\n" +
                "CustomData2.Z  →  溶解阈值\n" +
                "CustomData2.W  →  全局透明度",
                MessageType.None);
            EditorGUI.indentLevel--;
        }
        EditorGUILayout.EndVertical();
    }

    // =====================================================
    // 工具函数
    // =====================================================
    void DrawSeparator()
    {
        Rect r = EditorGUILayout.GetControlRect(false, 1f);
        EditorGUI.DrawRect(r, new Color(0.5f, 0.5f, 0.5f, 0.4f));
        GUILayout.Space(3);
    }

    void DrawBlendPopup(MaterialEditor me, MaterialProperty[] props)
    {
        MaterialProperty srcProp = FindProperty("_Scr", props, false);
        MaterialProperty dstProp = FindProperty("_Dst", props, false);
        if (srcProp == null || dstProp == null) return;

        int src = (int)srcProp.floatValue;
        int dst = (int)dstProp.floatValue;
        int cur = 0;
        for (int i = 0; i < BlendSrcValues.Length; i++)
            if (BlendSrcValues[i] == src && BlendDstValues[i] == dst) { cur = i; break; }

        EditorGUI.BeginChangeCheck();
        int sel = EditorGUILayout.Popup("混合模式", cur, BlendNames);
        if (EditorGUI.EndChangeCheck())
        {
            me.RegisterPropertyChangeUndo("混合模式");
            srcProp.floatValue = BlendSrcValues[sel];
            dstProp.floatValue = BlendDstValues[sel];
        }
    }

    void DrawZTestPopup(MaterialEditor me, MaterialProperty[] props)
    {
        MaterialProperty p = FindProperty("_ZTest", props, false);
        if (p == null) return;

        int cur = 0;
        for (int i = 0; i < ZTestValues.Length; i++)
            if (ZTestValues[i] == (int)p.floatValue) { cur = i; break; }

        EditorGUI.BeginChangeCheck();
        int sel = EditorGUILayout.Popup("深度测试", cur, ZTestNames);
        if (EditorGUI.EndChangeCheck())
        {
            me.RegisterPropertyChangeUndo("深度测试");
            p.floatValue = ZTestValues[sel];
        }
    }

    void DrawCullPopup(MaterialEditor me, MaterialProperty[] props)
    {
        MaterialProperty p = FindProperty("_Cull", props, false);
        if (p == null) return;

        int cur = 0;
        for (int i = 0; i < CullValues.Length; i++)
            if (CullValues[i] == (int)p.floatValue) { cur = i; break; }

        EditorGUI.BeginChangeCheck();
        int sel = EditorGUILayout.Popup("剔除模式", cur, CullNames);
        if (EditorGUI.EndChangeCheck())
        {
            me.RegisterPropertyChangeUndo("剔除模式");
            p.floatValue = CullValues[sel];
        }
    }

    void DrawRenderQueuePopup(MaterialEditor me)
    {
        Material mat = me.target as Material;
        
        int cur = 0;
        for (int i = 0; i < RenderQueueValues.Length; i++)
        {
            if (RenderQueueValues[i] == mat.renderQueue) { cur = i; break; }
        }

        EditorGUI.BeginChangeCheck();
        int sel = EditorGUILayout.Popup("Render Queue", cur, RenderQueueNames);
        if (EditorGUI.EndChangeCheck())
        {
            me.RegisterPropertyChangeUndo("Render Queue");
            mat.renderQueue = RenderQueueValues[sel];
        }
    }

    void SafeDraw(MaterialEditor me, MaterialProperty[] props, string name, string label)
    {
        MaterialProperty p = FindProperty(name, props, false);
        if (p != null) me.ShaderProperty(p, label);
    }

    bool IsEnabled(MaterialProperty[] props, string name)
    {
        MaterialProperty p = FindProperty(name, props, false);
        return p != null && p.floatValue > 0.5f;
    }
}
#endif

