function balance2svg(balance_array) {
	var svg = document.getElementById('chart-frame');
	var svgdoc = svg.contentDocument;
	var tttarget = svgdoc.getElementById('tttarget');
	tttarget.setAttribute('x', 100);
	var rect = document.createElementNS(svg.namespaceURI, 'rect');
	/*
	rect.setAttribute('x', 55);
	rect.setAttribute('y', 55);
	rect.setAttribute('width', 500);
	rect.setAttribute('height', 500);
	rect.setAttribute('fill','#95B3D7');
	svg.appendChild(rect);
	*/
}
//the axes have fixed gridlines, we just need to alter the value at each line
function set_x_axis_values(lowval, highval) {
}
function set_y_axis_values(lowval, highval) {
}
