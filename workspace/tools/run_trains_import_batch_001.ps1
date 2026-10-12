$ErrorActionPreference = 'Stop'
$items = @(
  @{ id='acid'; family='acid'; rel='Battle\Fx_acid\eff\Fx_acid.prefab' },
  @{ id='ice_spike'; family='ice'; rel='Battle\Fx_BDSX_bingzhui\Fx_BDSX_bignzhui.prefab' },
  @{ id='shield'; family='shield'; rel='Battle\Fx_com_sheilder\Fx_com_sheilder.prefab' },
  @{ id='thunder_ball'; family='lightning'; rel='Battle\Fx_ThunderBall\eff\Fx_ThunderBall.prefab' },
  @{ id='scene_explosion'; family='explosion'; rel='Scene\Fx_explosion\eff\Fx_Scene_explosion_01.prefab' },
  @{ id='scene_smoke'; family='smoke'; rel='Scene\Fx_smoke\eff\Fx_Scene_smoke_01.prefab' },
  @{ id='whirwind'; family='wind'; rel='Battle\Fx_whirwind\eff\Fx_whirwind.prefab' }
)
foreach ($item in $items) {
  $source = "E:\Trains\Unity\Assets\ArtResources\FX\$($item.rel)"
  $sampleName = "Trains_$($item.id)_001"
  $sourceId = "SRC-TRAINS-$($item.id.ToUpper())-001"
  $outputDir = "workspace/data/vfx_generation/sources/$sampleName"
  $args = @('-m','workspace.tools.vfx_source_ingest','--source',$source,'--output-dir',$outputDir,'--source-id',$sourceId,'--title',$item.id,'--effect-family',$item.family,'--source-unity-project','E:\Trains\Unity','--target-unity-project','UnityDemo\EffectDemo','--copy-assets','--copy-dependency-closure','--resolve-project-guids','--copy-name',$sampleName,'--shared-dependency-store','Assets/VFXSourceIngest/Shared','--dedupe-by','sha256','--rewrite-guid-references','--hash-files','--beads-id','vfx-2df.19','--project-guid-cache','workspace/data/vfx_generation/guid_cache/trains_unity_assets.json','--overwrite')
  $output = & python @args 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Re-import failed for $($item.id): $output" }
  Write-Output "REIMPORTED $($item.id)"
}
