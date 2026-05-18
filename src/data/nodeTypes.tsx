import { memo } from 'react';
import * as N from '../components/Nodes';
import { withNodeResizer } from '../hocs/withNodeResizer';

const withNodeColor = (Component: React.ComponentType<any>) =>
  memo(({ selected, data, ...props }: any) => {
    const cIdx = data?.params?.color_index;
    const palIdx = data?.activePaletteIndex ?? 6;
    const customBg = cIdx !== undefined
      ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.bg
      : data?.params?.bg_color;
    const customText = cIdx !== undefined
      ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.dark
      : data?.params?.text_color;
    return (
      <N.NodeColorProvider value={{ customBg, customText }}>
        <Component selected={selected} data={data} {...props} />
      </N.NodeColorProvider>
    );
  });

const ColoredGenericCustomNode = withNodeColor(N.GenericCustomNode);

const getNoteColor = (data: any) => {
  const cIdx = data?.params?.color_index;
  const palIdx = data?.activePaletteIndex ?? 6;
  const bg = cIdx !== undefined ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#ffd4b8');
  return bg + '99';
};
const getFrameColor = (data: any) => {
  const cIdx = data?.params?.color_index;
  const palIdx = data?.activePaletteIndex ?? 6;
  return cIdx !== undefined ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#333333');
};

const _baseNodeTypes: Record<string, React.ComponentType<any>> = {
  input_webcam: N.InputWebcamNode,
  input_image: N.InputImageNode,
  input_movie: N.InputMovieNode,
  input_solid_color: N.SolidColorNode,
  filter_canny: N.FilterCannyNode,
  plugin_gradient: N.FilterGradientNode,
  filter_color_mask: N.FilterColorMaskNode,
  mask_operations: N.MaskOperationsNode,
  plugin_invert_mask: N.GenericCustomNode,
  filter_blur: N.FilterBlurNode,
  filter_gray: N.FilterGrayNode,
  filter_threshold: N.FilterThresholdNode,
  filter_morphology: N.FilterMorphologyNode,
  filter_morphology_smart: N.FilterMorphologySmartNode,
  geom_flip: N.GeomFlipNode,
  geom_resize: N.GeomResizeNode,
  geom_crop_rect: N.CropRectNode,
  geom_obb: N.GenericCustomNode,
  depth_anything_v2: N.GenericCustomNode,
  forensic_footprint: N.ForensicFootprintNode,
  tool_annotator: N.AnnotatorNode,
  analysis_face_mp: N.AnalysisFaceMPNode,
  analysis_hand_mp: N.AnalysisHandMPNode,
  analysis_pose_mp: N.AnalysisPoseMPNode,
  analysis_head_pose: N.AnalysisHeadPoseNode,
  transform_eye_crop: N.TransformEyeCropNode,
  analysis_gaze: N.AnalysisGazeNode,
  math_vec_to_screen: N.MathVecToScreenNode,
  analysis_flow: N.AnalysisFlowNode,
  analysis_flow_viz: N.AnalysisFlowVizNode,
  analysis_monitor: N.AnalysisMonitorNode,
  geo_statistics: N.GeoStatisticsNode,
  sam_grain_stats: N.GenericCustomNode,
  fast_sam_segmenter: N.GenericCustomNode,
  geo_land_cover: N.GenericCustomNode,
  sci_analysis_report: N.ScientificReportNode,
  geo_petro_tableau: N.PetrographicReportNode,
  geo_grain_histogram: withNodeResizer(N.GrainHistogramNode, 260, 200),
  sci_kmeans_list: N.GenericCustomNode,
  sci_interactive_calibration: N.InteractiveCalibrationNode,
  sci_visual_measure: N.VisualMeasureNode,
  feat_visual_size_gate: N.VisualSizeGateNode,
  feat_mask_stats: N.GenericCustomNode,
  feat_bilateral: N.GenericCustomNode,
  feat_clahe: N.GenericCustomNode,
  feat_hough_circles: N.GenericCustomNode,
  feat_list_aggregator: N.GenericCustomNode,
  util_mask_band: N.GenericCustomNode,
  util_split_half: N.GenericCustomNode,
  util_roi_polygon: N.ROIPolygonNode,
  util_landmark_selector: N.UtilLandmarkSelectorNode,
  draw_overlay: N.DrawOverlayNode,
  draw_tint_mask: N.GenericCustomNode,
  draw_point: N.GenericCustomNode,
  draw_line: N.GenericCustomNode,
  draw_rect: N.GenericCustomNode,
  util_coord_to_mask: N.UtilCoordToMaskNode,
  util_mask_blend: N.UtilMaskBlendNode,
  data_list_selector: N.DataListSelectorNode,
  list_region_select: N.RegionSelectorNode,
  data_coord_splitter: N.DataCoordSplitterNode,
  data_coord_combine: N.DataCoordCombineNode,
  util_dict_merge: N.DictMergeNode,
  data_inspector: withNodeResizer(N.DataInspectorNode, 180, 120),
  output_display: N.OutputDisplayNode,
  logic_python: N.PythonNode,
  mask_point_query: N.MaskPointQueryNode,
  canvas_note: withNodeResizer(N.CanvasNoteNode, 120, 60, getNoteColor),
  canvas_reroute: N.CanvasRerouteNode,
  output_movie: N.OutputMovieNode,
  geo_band_stats: N.RasterStatsNode,
  sci_matrix_dist: withNodeResizer(N.MatrixDistNode, 220, 160),
  math_add: N.MathNode,
  math_sub: N.MathNode,
  math_mul: N.MathNode,
  math_div: N.MathNode,
  math_mod: N.MathNode,
  math_min: N.MathNode,
  math_max: N.MathNode,
  math_pow: N.MathNode,
  math_abs: N.MathNode,
  math_round: N.MathNode,
  math_sin: N.MathNode,
  math_cos: N.MathNode,
  math_clamp: N.MathNode,
  math_distance: N.MathNode,
  plugin_audio_input: N.AudioInputNode,
  plugin_audio_playback: N.AudioPlaybackNode,
  plugin_audio_waveform: N.AudioWaveformNode,
  plugin_audio_to_spectrogram: N.AudioToSpectroNode,
  plugin_spectrogram_to_audio: N.SpectroToAudioNode,
  plugin_audio_freq_filter: N.AudioGenericNode,
  plugin_audio_pitch_shift: N.AudioGenericNode,
  plugin_audio_time_stretch: N.AudioGenericNode,
  plugin_audio_info: N.AudioGenericNode,
  plugin_audio_export: N.AudioExportNode,
  string_input: N.StringNode,
  string_concat: N.StringNode,
  string_split: N.StringNode,
  string_length: N.StringNode,
  string_case: N.StringNode,
  string_replace: N.StringNode,
  canvas_frame: withNodeResizer(N.CanvasFrameNode, 200, 150, getFrameColor),
  canvas_teleport: N.TeleportNode,
  sci_plotter: withNodeResizer(N.ScientificPlotterNode, 240, 180),
  plotter_pro: withNodeResizer(N.PlotterProNode, 240, 180),
  sci_histogram: withNodeResizer(N.ScientificHistogramNode, 250, 180),
  sci_calibration: N.ScientificCalibrationNode,
  group_node: N.GroupNode,
  group_input: N.GroupInputNode,
  group_output: N.GroupOutputNode,
  export_py: N.ExportPyNode,
  manual_points: N.ManualPointsNode,
  hema_hemogramme: N.HemogrammeNode,
};

export const nodeTypes: Record<string, React.ComponentType<any>> = Object.fromEntries(
  Object.entries(_baseNodeTypes).map(([k, v]) => [k, withNodeColor(v)])
);

export { withNodeColor, ColoredGenericCustomNode };
