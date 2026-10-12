Shader "Hidden/EffectDemo/MaterialStateProbe"
{
    Properties
    {
        _MainTex ("Main Texture", 2D) = "white" {}
        _TintColor ("Tint Color", Color) = (1,1,1,1)
        _DissolveAmount ("Dissolve Amount", Range(0,1)) = 0
        _FlowSpeed ("Flow Speed", Float) = 0
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Off
        ZWrite Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma shader_feature_local __ PROBE_FLOW_ON
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;
            float4 _TintColor;
            float _DissolveAmount;
            float _FlowSpeed;
            float _EffectDemoTrackedGlobalAlpha;

            v2f vert(appdata input)
            {
                v2f output;
                output.vertex = UnityObjectToClipPos(input.vertex);
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                return output;
            }

            fixed4 frag(v2f input) : SV_Target
            {
                float2 uv = input.uv;
                #if PROBE_FLOW_ON
                uv.x += _Time.y * _FlowSpeed * 0.05;
                #endif
                fixed4 color = tex2D(_MainTex, uv) * _TintColor;
                color.a *= _EffectDemoTrackedGlobalAlpha;
                float mask = frac(input.uv.x * 5.0 + input.uv.y * 3.0);
                clip(mask - _DissolveAmount);
                return color;
            }
            ENDCG
        }
    }
}
