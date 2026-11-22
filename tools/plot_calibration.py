"""Render a calibration JSON report to a labeled SVG (optional ReportLab dependency)."""
import argparse
import json
import math
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.charts.lineplots import ScatterPlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib.colors import HexColor


def render(report, out):
    rows = report['builds']
    if not rows:
        raise ValueError('a scatterplot needs at least one matched build')
    drawing = Drawing(560, 325)
    chart = ScatterPlot()
    chart.x, chart.y, chart.width, chart.height = 62, 45, 425, 210
    chart.xLabel = chart.yLabel = ''
    chart.lineLabelFormat = None
    chart.data = [[(r['local'],r['official']) for r in rows]]
    chart.lines[0].symbol = makeMarker('FilledCircle')
    chart.lines[0].symbol.fillColor = HexColor('#166a74')
    chart.lines[0].symbol.strokeColor = HexColor('#166a74')
    for axis, field in [(chart.xValueAxis,'local'), (chart.yValueAxis,'official')]:
        values = [r[field] for r in rows]
        pad = max(.05,(max(values)-min(values))*.15)
        axis.valueMin = math.floor((min(values)-pad)*10)/10
        axis.valueMax = math.ceil((max(values)+pad)*10)/10
        axis.labels.fontSize = 10
        axis.labelTextFormat = '%.1f'
    drawing.add(chart.draw())
    for row in rows:
        x = chart.xValueAxis.scale(row['local'])
        y = chart.yValueAxis.scale(row['official'])
        drawing.add(String(x+7,y+3,row['label'],fontName='Courier',fontSize=10))
    drawing.add(String(32,300,'Local and official placement points',fontName='Helvetica-Bold',fontSize=18))
    drawing.add(String(32,277,f"Reported official mean   ·   {len(rows)} builds",fontSize=11))
    drawing.add(String(270,10,'Mean local placement points',textAnchor='middle',fontSize=11))
    renderSVG.drawToFile(drawing,str(out))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('out',type=Path)
    args=parser.parse_args()
    render(json.loads(args.report.read_text()),args.out)
