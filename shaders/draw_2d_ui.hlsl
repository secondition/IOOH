// 2D UI绘制着色器
// 用于在游戏中绘制带纹理的2D界面元素
// 基于Snaccubus的draw_2d.hlsl实现

Texture1D<float4> IniParams : register(t120);

// 从ini文件读取的参数
// x87 = 宽度 (相对屏幕宽度，例如0.3表示30%屏幕宽度)
// y87 = 高度 (相对屏幕高度)
// z87 = X位置 (相对坐标，0-1)
// w87 = Y位置 (相对坐标，0-1)
#define SIZE IniParams[87].xy
#define OFFSET IniParams[87].zw

struct vs2ps {
    float4 pos : SV_Position0;
    float2 uv : TEXCOORD1;
};

#ifdef VERTEX_SHADER
void main(
        out vs2ps output,
        uint vertex : SV_VertexID)
{
    float2 BaseCoord, Offset;
    
    // 转换为NDC坐标系 (Normalized Device Coordinates)
    // NDC: X: -1(左) 到 1(右), Y: -1(下) 到 1(上)
    Offset.x = OFFSET.x * 2 - 1;
    Offset.y = (1 - OFFSET.y) * 2 - 1;
    BaseCoord.xy = float2((2 * SIZE.x), (2 * (-SIZE.y)));
    
    // 使用triangle strip生成四边形
    // 顶点顺序: 右上, 右下, 左上, 左下
    switch(vertex) {
        case 0: // 右上角
            output.pos.xy = float2(BaseCoord.x + Offset.x, BaseCoord.y + Offset.y);
            output.uv = float2(1, 0);
            break;
        case 1: // 右下角
            output.pos.xy = float2(BaseCoord.x + Offset.x, 0 + Offset.y);
            output.uv = float2(1, 1);
            break;
        case 2: // 左上角
            output.pos.xy = float2(0 + Offset.x, BaseCoord.y + Offset.y);
            output.uv = float2(0, 0);
            break;
        case 3: // 左下角
            output.pos.xy = float2(0 + Offset.x, 0 + Offset.y);
            output.uv = float2(0, 1);
            break;
        default:
            output.pos.xy = 0;
            output.uv = float2(0, 0);
            break;
    };
    
    output.pos.zw = float2(0, 1);
}
#endif

#ifdef PIXEL_SHADER
Texture2D<float4> tex : register(t100);

void main(vs2ps input, out float4 result : SV_Target0)
{
    uint width, height;
    tex.GetDimensions(width, height);
    
    // 如果纹理无效，丢弃像素
    if (!width || !height) discard;
    
    // 翻转Y坐标（DDS纹理通常是上下颠倒的）
    input.uv.y = 1 - input.uv.y;
    
    // 采样纹理
    result = tex.Load(int3(input.uv.xy * float2(width, height), 0));
    
    // 如果alpha接近0，丢弃像素（完全透明）
    if (result.a < 0.01) discard;
}
#endif
