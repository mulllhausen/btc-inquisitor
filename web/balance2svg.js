var fifty_days_in_seconds = 50 * 24 * 60 * 60;
var all_currencies_zero = {'sat': 0, 'btc': 0, 'local': 0};
var svg_x_size = 800;
var svg_y_size = 300;
function balance2svg(balance_json) {
	svgdoc = document.getElementById('chart-frame').contentDocument;
	graph_area = svgdoc.getElementById('graph-area'); //used later

	//prepend [xmin, {0,0,0}] - everybody had 0 btc before bitcoin existed
	balance_json.unshift([balance_json[0][0], all_currencies_zero]);
	var balance_json = balance_rel2abs(balance_json);

	//append [xmax, {0,0,0}] - close the poly
	balance_json.push([
		balance_json[balance_json.length - 1][0], all_currencies_zero
	]);
	var x_range = get_range('x', balance_json);
	set_axis_values('x', x_range['min'], x_range['max']);

	var y_range = get_range('y', balance_json);
	set_axis_values('y', y_range['min']['sat'], y_range['max']['sat']);

	var svg_dims = balance_json2svg_dims(balance_json, x_range, y_range);
	var poly_points_str = svg_dims2poly_points_str(svg_dims);
	update_poly(0, poly_points_str);

	var tttarget = svgdoc.getElementById('tttarget');
	tttarget.setAttribute('cx', 100);

	//setup the click events on the heading
	setup_heading_click_events();
}
function setup_heading_click_events() {
	svg_heading_positions = 'btc,satoshis,local'; //init
	btc_heading_animate = svgdoc.getElementById('btc-heading-animate');
	satoshis_heading_animate = svgdoc.getElementById('satoshis-heading-animate');
	local_currency_heading_animate = svgdoc.getElementById('local-currency-heading-animate');

	svgdoc.getElementById('btc-heading').onclick = function() {
		switch(svg_heading_positions) {
			case 'btc,local,satoshis': //swap btc and local headings
				btc_heading_animate.setAttribute('from', '0,0');
				btc_heading_animate.setAttribute('to', '60,0');
				btc_heading_animate.beginElement();

				local_currency_heading_animate.setAttribute('from', '60,0');
				local_currency_heading_animate.setAttribute('to', '0,0');
				local_currency_heading_animate.beginElement();

				svg_heading_positions = 'local,btc,satoshis';
				break;
			case 'btc,satoshis,local': //swap btc and satoshis headings
				btc_heading_animate.setAttribute('from', '0,0');
				btc_heading_animate.setAttribute('to', '100,0');
				btc_heading_animate.beginElement();

				satoshis_heading_animate.setAttribute('from', '60,0');
				satoshis_heading_animate.setAttribute('to', '0,0');
				satoshis_heading_animate.beginElement();

				svg_heading_positions = 'satoshis,btc,local';
				break;
			case 'local,btc,satoshis': //btc already in the center
				break;
			case 'local,satoshis,btc': //swap btc and satoshis headings
				btc_heading_animate.setAttribute('from', '160,0');
				btc_heading_animate.setAttribute('to', '60,0');
				btc_heading_animate.beginElement();

				satoshis_heading_animate.setAttribute('from', '60,0');
				satoshis_heading_animate.setAttribute('to', '120,0');
				satoshis_heading_animate.beginElement();

				svg_heading_positions = 'local,btc,satoshis';
				break;
			case 'satoshis,local,btc': //swap btc and local headings
				btc_heading_animate.setAttribute('from', '160,0');
				btc_heading_animate.setAttribute('to', '100,0');
				btc_heading_animate.beginElement();

				local_currency_heading_animate.setAttribute('from', '100,0');
				local_currency_heading_animate.setAttribute('to', '160,0');
				local_currency_heading_animate.beginElement();

				svg_heading_positions = 'satoshis,btc,local';
				break;
			case 'satoshis,btc,local': //btc already at the center
				break;
		}
	};
	svgdoc.getElementById('satoshis-heading').onclick = function() {
		switch(svg_heading_positions) {
			case 'btc,local,satoshis': //swap satoshis and local headings
				satoshis_heading_animate.setAttribute('from', '120,0');
				satoshis_heading_animate.setAttribute('to', '60,0');
				satoshis_heading_animate.beginElement();

				local_currency_heading_animate.setAttribute('from', '60,0');
				local_currency_heading_animate.setAttribute('to', '160,0');
				local_currency_heading_animate.beginElement();

				svg_heading_positions = 'btc,satoshis,local';
				break;
			case 'btc,satoshis,local': //satoshis already at the center
				break;
			case 'local,btc,satoshis': //swap satoshis and btc headings
				satoshis_heading_animate.setAttribute('from', '120,0');
				satoshis_heading_animate.setAttribute('to', '60,0');
				satoshis_heading_animate.beginElement();

				btc_heading_animate.setAttribute('from', '60,0');
				btc_heading_animate.setAttribute('to', '160,0');
				btc_heading_animate.beginElement();

				svg_heading_positions = 'local,satoshis,btc';
				break;
			case 'local,satoshis,btc': //satoshis already at the center
				break;
			case 'satoshis,local,btc': //swap satoshis and local headings
				satoshis_heading_animate.setAttribute('from', '0,0');
				satoshis_heading_animate.setAttribute('to', '60,0');
				satoshis_heading_animate.beginElement();

				local_currency_heading_animate.setAttribute('from', '100,0');
				local_currency_heading_animate.setAttribute('to', '0,0');
				local_currency_heading_animate.beginElement();

				svg_heading_positions = 'local,satoshis,btc';
				break;
			case 'satoshis,btc,local': //swap satoshis and btc headings
				satoshis_heading_animate.setAttribute('from', '0,0');
				satoshis_heading_animate.setAttribute('to', '60,0');
				satoshis_heading_animate.beginElement();

				btc_heading_animate.setAttribute('from', '100,0');
				btc_heading_animate.setAttribute('to', '0,0');
				btc_heading_animate.beginElement();

				svg_heading_positions = 'btc,satoshis,local';
				break;
		}
	};
	svgdoc.getElementById('local-currency-heading').onclick = function() {
		switch(svg_heading_positions) {
			case 'btc,local,satoshis': //local currency already at the center
				break;
			case 'btc,satoshis,local': //swap local currency and satoshis
				local_currency_heading_animate.setAttribute('from', '160,0');
				local_currency_heading_animate.setAttribute('to', '60,0');
				local_currency_heading_animate.beginElement();

				satoshis_heading_animate.setAttribute('from', '60,0');
				satoshis_heading_animate.setAttribute('to', '120,0');
				satoshis_heading_animate.beginElement();

				svg_heading_positions = 'btc,local,satoshis';
				break;
			case 'local,btc,satoshis': //swap local currency and btc headings
				local_currency_heading_animate.setAttribute('from', '0,0');
				local_currency_heading_animate.setAttribute('to', '60,0');
				local_currency_heading_animate.beginElement();

				btc_heading_animate.setAttribute('from', '60,0');
				btc_heading_animate.setAttribute('to', '0,0');
				btc_heading_animate.beginElement();

				svg_heading_positions = 'btc,local,satoshis';
				break;
			case 'local,satoshis,btc': //swap local currency and satoshis
				local_currency_heading_animate.setAttribute('from', '0,0');
				local_currency_heading_animate.setAttribute('to', '100,0');
				local_currency_heading_animate.beginElement();

				satoshis_heading_animate.setAttribute('from', '60,0');
				satoshis_heading_animate.setAttribute('to', '0,0');
				satoshis_heading_animate.beginElement();

				svg_heading_positions = 'satoshis,local,btc';
				break;
			case 'satoshis,local,btc': //local currency already at the center
				break;
			case 'satoshis,btc,local': //swap local and btc headings
				local_currency_heading_animate.setAttribute('from', '160,0');
				local_currency_heading_animate.setAttribute('to', '100,0');
				local_currency_heading_animate.beginElement();

				btc_heading_animate.setAttribute('from', '100,0');
				btc_heading_animate.setAttribute('to', '160,0');
				btc_heading_animate.beginElement();

				svg_heading_positions = 'satoshis,local,btc';
				break;
		}
	};
}
function balance_rel2abs(balance_json) {
	var satoshis = 0; //init
	var btc = 0; //init
	var local = 0; //init
	for(var i = 0; i < balance_json.length; i++) {
		var change_in_satoshis = balance_json[i][1]['sat'];
		var change_in_btc = balance_json[i][1]['btc'];
		var change_in_local = balance_json[i][1]['local'];
		satoshis += change_in_satoshis;
		btc += change_in_btc;
		local += change_in_local;
		balance_json[i][1]['sat'] = satoshis;
		balance_json[i][1]['btc'] = btc;
		balance_json[i][1]['local'] = local;
	}
	return balance_json;
}
function balance_json2svg_dims(balance_json, x_range, y_range) {
	var svg_dims = [];
	var x_abs = x_range['max'] - x_range['min'];
	var y_abs = y_range['max']['sat'] - y_range['min']['sat'];
	for(var i = 0; i < balance_json.length; i++) {
		var svg_x = svg_x_size * (balance_json[i][0] - x_range['min']) / x_abs;
		var svg_y = svg_y_size * (balance_json[i][1]['sat'] - y_range['min']) / y_abs;
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
	var currency_min = {'sat': min, 'btc': min, 'local': min};
	var currency_max = {'sat': max, 'btc': max, 'local': max};
	var currencies = ['sat', 'btc', 'local'];
	for(var i = 0; i < balance_json.length; i++) {
		switch(x_or_y) {
			case 'x':
				var value = balance_json[i][0];
				if(value < min) min = value;
				if(value > max) max = value;
				break;
			case 'y':
				for(var j = 0; j < 3; j++) {
					var cur = currencies[j];
					var value = balance_json[i][1][cur];
					if(value < currency_min[cur]) currency_min[cur] = value;
					if(value > currency_max[cur]) currency_max[cur] = value;
				}
				break;
		}
	}
	switch(x_or_y) {
		case 'x':
			min = min - (0.1 * (max - min)); //10% under min
			return {'min': min, 'max': max};
		case 'y':
			for(var j = 0; j < 3; j++) {
				var cur = currencies[j];
				currency_max[cur] *= 1.1; //10% over max. works because min = 0
			}
			return {'min': currency_min, 'max': currency_max};
	}
}
function svg_dims2poly_points_str(svg_dims) {
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
