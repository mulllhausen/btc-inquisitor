function balance2svg(balance_json) {
	svgdoc = document.getElementById('chart-frame').contentDocument;
	graph_area = svgdoc.getElementById('graph-area'); //used later
	svg_x_size = 800;
	svg_y_size = 300;

	balance_json.unshift([balance_json[0][0], 0]); //xmin,0
	var balance_json = balance_rel2abs(balance_json);
	balance_json.push([balance_json[balance_json.length - 1][0], 0]); //xmax,0

	var x_range = get_range('x', balance_json);
	set_axis_values('x', x_range['min'], x_range['max']);

	var y_range = get_range('y', balance_json);
	set_axis_values('y', y_range['min'], y_range['max']);

	var svg_dims = balance_json2svg_dims(balance_json, x_range, y_range);
	var poly_points_str = balance_json2poly_points_str(svg_dims);
	update_poly(0, poly_points_str);

	var tttarget = svgdoc.getElementById('tttarget');
	tttarget.setAttribute('cx', 100);
}
function balance_rel2abs(balance_json) {
	var satoshis = 0;
	for(var i = 0; i < balance_json.length; i++) {
		var change_in_satoshis = balance_json[i][1];
		satoshis += change_in_satoshis;
		balance_json[i][1] = satoshis;
	}
	return balance_json;
}
function balance_json2svg_dims(balance_json, x_range, y_range) {
	var svg_dims = [];
	var x_abs = x_range['max'] - x_range['min'];
	var y_abs = y_range['max'] - y_range['min'];
	for(var i = 0; i < balance_json.length; i++) {
		var svg_x = svg_x_size * (balance_json[i][0] - x_range['min']) / x_abs;
		var svg_y = svg_y_size * (balance_json[i][1] - y_range['min']) / y_abs;
		svg_dims[i] = [svg_x, svg_y];
	}
	return svg_dims;
}
function update_poly(poly_num, poly_points_str) {
	var poly = svgdoc.getElementById('poly' + poly_num);
	poly.setAttribute('points', poly_points_str);
}
//the axes have fixed gridlines, we just need to alter the value at each line
function set_axis_values(x_or_y, lowval, highval) {
	//use 0 <= x <= svg_x_size or 0 <= y <= svg_y_size. beyond this is out of
	//bounds
	var num_dashlines = 4;
	switch(x_or_y) {
		case 'x':
			var id_str_start = 'vertical-dashline';
			var svg_chart_max = svg_x_size;
			var display_value_translated = unixtime2datetime_str(lowval);
			break;
		case 'y':
			var id_str_start = 'horizontal-dashline';
			var svg_chart_max = svg_y_size;
			var display_value_translated = one_dp(lowval);
			break;
	}
	var this_id_num = 0; //init
	var this_id_str = id_str_start + this_id_num;
	var dashline0 = svgdoc.getElementById(this_id_str);
	var position_spacing = svg_chart_max / (num_dashlines + 1);
	var display_value = lowval; //init
	dashline0.children[0].textContent = display_value_translated;
	var display_spacing = (highval - lowval) / (num_dashlines + 1);
	var position = 0; //init
	for(var i = 0; i <= num_dashlines; i++) {
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
		switch(x_or_y) {
			case 'x':
				position_absolutely(newelement, position, null);
				display_value_translated = unixtime2datetime_str(display_value);
				break;
			case 'y':
				position_absolutely(newelement, null, position);
				display_value_translated = one_dp(display_value);
				break;
		}
		newelement.children[0].textContent = display_value_translated;
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
function get_range(x_or_y, balance_json) {
	var min = 99999999999999999; //init to the largest conceivable number
	var max = -99999999999999999; //init to the smallest conceivable number
	var j = (x_or_y == 'x') ? 0 : 1;
	for(var i = 0; i < balance_json.length; i++) {
		if(balance_json[i][j] < min) min = balance_json[i][j];
		if(balance_json[i][j] > max) max = balance_json[i][j];
	}
	switch(x_or_y) {
		case 'x':
			break;
		case 'y':
			max *= 1.1;
			break;
	}
	return {'min': min, 'max': max};
}
function balance_json2poly_points_str(svg_dims) {
	var poly_points_list = [];
	var prev_y = 0; //init
	for(var i = 0; i < svg_dims.length; i++) {
		var x = svg_dims[i][0];
		var y = svg_dims[i][1];
		poly_points_list.push([x, prev_y]);
		poly_points_list.push([x, y]);
		prev_y = y;
	}
	return poly_points_list.join(' ');
}
function unixtime2datetime_str(unixtime) {
	var d = new Date(unixtime * 1000);
	return d.toISOString().slice(0, 10) + ' ' + d.getHours() + ":" +
	d.getMinutes() + ':' + d.getSeconds();
}
