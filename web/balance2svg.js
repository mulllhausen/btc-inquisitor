function balance2svg(balance_array) {
	svgdoc = document.getElementById('chart-frame').contentDocument;
	graph_area = svgdoc.getElementById('graph-area');
	//var graph_area_coordinates = graph_area.getBoundingClientRect();
	var tttarget = svgdoc.getElementById('tttarget');
	set_x_axis_values(150, 750);
	set_y_axis_values(0, 20);
	tttarget.setAttribute('cx', 100);
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
	//use 0 <= x <= 840. beyond this is out of bounds
	//divide the axis into 8 points with x = 0 at the lowval and x = 840 at the
	//highval
	var a_vertical_dashline = svgdoc.getElementById('vertical-dashline0');
	var display_dashlines = 8;
	var spacing = 840 / (display_dashlines + 1);
	var x = 0; //init
	for(i = 0; i <= display_dashlines; i++) {
		x += spacing;
		var newelement = a_vertical_dashline.cloneNode(true);
		graph_area.appendChild(newelement);
		pos_absolutely(newelement, x, null);
	}
}
function set_y_axis_values(lowval, highval) {
	//use 0 <= y <= 340. beyond this is out of bounds
	var a_horizontal_dashline = svgdoc.getElementById('horizontal-dashline0');
	a_horizontal_dashline.children[0].textContent = 'qwe';
	var display_dashlines = 8;
	var spacing = 340 / (display_dashlines + 1);
	var y = 0; //init
	for(i = 0; i <= display_dashlines; i++) {
		y += spacing;
		var newelement = a_horizontal_dashline.cloneNode(true);
		graph_area.appendChild(newelement);
		pos_absolutely(newelement, null, y);
	}
}
function pos_absolutely(el, x, y)
{
	var matrix = el.transform.baseVal.getItem(0).matrix;
	if(x !== null) matrix.e = x;
	if(y !== null) matrix.f = y;
}
