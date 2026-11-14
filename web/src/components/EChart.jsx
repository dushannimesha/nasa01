import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { INK } from "../lib/data.js";

echarts.use([BarChart, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, SVGRenderer]);

// Shared look: recessive grid and axes, text in ink tokens, system font.
export const axis = (extra = {}) => ({
  axisLine: { lineStyle: { color: INK.axis } },
  axisTick: { show: false },
  axisLabel: { color: INK.muted, fontSize: 11 },
  splitLine: { lineStyle: { color: INK.grid } },
  nameTextStyle: { color: INK.muted, fontSize: 11, align: "left", padding: [0, 0, 0, -30] },
  nameGap: 12,
  ...extra,
});
export const baseOption = {
  textStyle: { fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: INK.secondary },
  grid: { left: 8, right: 16, top: 52, bottom: 8, containLabel: true },
  tooltip: { trigger: "axis", backgroundColor: "#fff", borderColor: INK.grid, textStyle: { color: INK.primary, fontSize: 12 }, axisPointer: { type: "shadow", shadowStyle: { color: "rgba(11,11,11,0.04)" } } },
  legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: INK.secondary, fontSize: 12 } },
  animationDuration: 250,
};

export default function EChart({ option, height = 260, label }) {
  const ref = useRef(null);
  const chart = useRef(null);
  useEffect(() => {
    chart.current = echarts.init(ref.current, null, { renderer: "svg" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.current?.dispose(); };
  }, []);
  useEffect(() => { chart.current?.setOption({ ...baseOption, ...option }, true); }, [option]);
  return <div ref={ref} role="img" aria-label={label} style={{ width: "100%", height }} />;
}
