function balance2svg(balance_array) {
	svgdoc = document.getElementById('chart-frame').contentDocument;
	graph_area = svgdoc.getElementById('graph-area');
	var tttarget = svgdoc.getElementById('tttarget');
	set_axis_values('x', 150, 750);
	set_axis_values('y', 0, 20);

	set_axis_values('x', 0, 800);
	set_axis_values('y', 0, 80);


	tttarget.setAttribute('cx', 100);
}
//the axes have fixed gridlines, we just need to alter the value at each line
function set_axis_values(x_or_y, lowval, highval) {
	//use 0 <= x <= 840. beyond this is out of bounds
	var num_dashlines = 6;
	switch(x_or_y) {
		case 'x':
			var id_str_start = 'vertical-dashline';
			var svg_chart_max = 840;
			break;
		case 'y':
			var id_str_start = 'horizontal-dashline';
			var svg_chart_max = 340;
			break;
	}
	var this_id_num = 0; //init
	var this_id_str = id_str_start + this_id_num;
	var dashline0 = svgdoc.getElementById(this_id_str);
	var position_spacing = svg_chart_max / (num_dashlines + 1);
	var display_value = lowval; //init
	dashline0.children[0].textContent = one_dp(display_value);
	var display_spacing = (highval - lowval) / (num_dashlines + 1);
	var position = 0; //init
	for(i = 0; i <= num_dashlines; i++) {
		this_id_num = i + 1;
		this_id_str = id_str_start + this_id_num;
		position += position_spacing;
		display_value += display_spacing;

		//if the element already exists then re-use it
		var newelement = svgdoc.getElementById(this_id_str);
		if(newelement === null) {
			var newelement = dashline0.cloneNode(true);
			graph_area.appendChild(newelement);
		}
		newelement = set_id(newelement, this_id_str);
		newelement.children[0].textContent = one_dp(display_value);
		switch(x_or_y) {
			case 'x': position_absolutely(newelement, position, null); break;
			case 'y': position_absolutely(newelement, null, position); break;
		}
	}
}
function one_dp(val) {
	//round number to 1 decimal place
	return Math.round(val * 10) / 10;
}
function position_absolutely(el, x, y) {
	var matrix = el.transform.baseVal.getItem(0).matrix;
	if(x !== null) matrix.e = x;
	if(y !== null) matrix.f = y;
}
function set_id(el, id_str) {
	//set the id for an element. this gets its own function in case a better way
	//of doing it is found in future. setAttribute() is known to be worse
	//(http://stackoverflow.com/a/4852404/339874)
	el.id = id_str;
	return el;
}
