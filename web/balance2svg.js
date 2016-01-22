function balance2svg(balance_array, svg) {
	var svgns = svg.namespaceURI;
	var rect = document.createElementNS(svgns,'rect');
	rect.setAttribute('x',5);
	rect.setAttribute('y',5);
	rect.setAttribute('width',500);
	rect.setAttribute('height',500);
	rect.setAttribute('fill','#95B3D7');
	svg.appendChild(rect);
}
