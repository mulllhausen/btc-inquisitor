var day_in_seconds = 24 * 60 * 60;
var all_currencies_zero = {'sat': 0, 'btc': 0, 'local': 0};
var svg_x_size = 800;
var svg_y_size = 300;
var done_init = false;
function init() {
	svgdoc = document.getElementById('chart-frame').contentDocument;
	graph_area = svgdoc.getElementById('graph-area'); //used later
	done_init = true;
}
function balance2svg(balance_json) {
	//you must pass in a complete list of balances - it cannot be incremental
	if(!done_init) init();

	//prepend [xmin, {0,0,0}] - everybody had 0 btc before bitcoin existed
	balance_json.unshift([balance_json[0][0], all_currencies_zero]);
	var balance_json = balance_rel2abs(balance_json);

	//append [xmax, {0,0,0}] - close the poly
	balance_json.push([
		balance_json[balance_json.length - 1][0], all_currencies_zero
	]);

	var num_x_divisions = 5; //the number of spaces between dates on the x-axis
	x_range = get_range('x', balance_json, num_x_divisions);
	set_axis_values('x', x_range['min'], x_range['max'], num_x_divisions);

	var num_y_divisions = 5; //the number of spaces between values on the y-axis
	y_range = get_range('y', balance_json, num_y_divisions);
	set_axis_values('y', y_range['min']['sat'], y_range['max']['sat'], num_y_divisions);

	var svg_dims = balance_json2svg_dims(balance_json, x_range, y_range);
	var poly_points_str = svg_dims2poly_points_str(svg_dims);
	update_poly(0, poly_points_str);

	var tttarget = svgdoc.getElementById('tttarget');
	tttarget.setAttribute('cx', 100);

	//setup the click events on the heading
	setup_heading_click_events(num_x_divisions, num_y_divisions);
	//init
	faders['fade_in_satoshis_box'].beginElement();
	faders['fade_in_satoshis_text'].beginElement();
}
function setup_heading_click_events(num_x_divisions, num_y_divisions) {
	//init globals so they are accessible for click events and state changes
	svg_heading_positions = 'btc,satoshis,local';
	btc_heading_animate = svgdoc.getElementById('btc-heading-animate');
	satoshis_heading_animate = svgdoc.getElementById('satoshis-heading-animate');
	local_currency_heading_animate = svgdoc.getElementById('local-currency-heading-animate');
	faders = {
		'fade_in_btc_box': svgdoc.getElementById('fade-in-btc-box'),
		'fade_in_btc_text': svgdoc.getElementById('fade-in-btc-text'),
		'fade_out_btc_box': svgdoc.getElementById('fade-out-btc-box'),
		'fade_out_btc_text': svgdoc.getElementById('fade-out-btc-text'),
		'fade_in_satoshis_box': svgdoc.getElementById('fade-in-satoshis-box'),
		'fade_in_satoshis_text': svgdoc.getElementById('fade-in-satoshis-text'),
		'fade_out_satoshis_box': svgdoc.getElementById('fade-out-satoshis-box'),
		'fade_out_satoshis_text': svgdoc.getElementById('fade-out-satoshis-text'),
		'fade_in_local_box': svgdoc.getElementById('fade-in-local-box'),
		'fade_in_local_text': svgdoc.getElementById('fade-in-local-text'),
		'fade_out_local_box': svgdoc.getElementById('fade-out-local-box'),
		'fade_out_local_text': svgdoc.getElementById('fade-out-local-text')
	};
	currency_headings = {
		'btc': svgdoc.getElementById('btc-heading'),
		'satoshis': svgdoc.getElementById('satoshis-heading'),
		'local-currency': svgdoc.getElementById('local-currency-heading')
	};
	currency_headings['btc'].onclick = function(num_y_divisions) {
		return function() {
			change_currency_state('btc');
			set_axis_values(
				'y', y_range['min']['btc'], y_range['max']['btc'],
				num_y_divisions
			);
		};
	}(num_y_divisions);

	currency_headings['satoshis'].onclick = function(num_y_divisions) {
		return function() {
			change_currency_state('satoshis');
			set_axis_values(
				'y', y_range['min']['sat'], y_range['max']['sat'],
				num_y_divisions
			);
		};
	}(num_y_divisions);

	currency_headings['local-currency'].onclick = function(num_y_divisions) {
		return function() {
			change_currency_state('local-currency');
			set_axis_values(
				'y', y_range['min']['local'], y_range['max']['local'],
				num_y_divisions
			);
		};
	}(num_y_divisions);

	headings_container = svgdoc.getElementById('headings-container');
}
function move_heading_horizontal(animation_element, from, to) {
	animation_element.setAttribute('from', from + ',0');
	animation_element.setAttribute('to', to + ',0');
	animation_element.beginElement();
}
function fade_heading_in_out(fade_in, fade_out) {
	faders['fade_in_' + fade_in + '_box'].beginElement();
	faders['fade_in_' + fade_in + '_text'].beginElement();
	faders['fade_out_' + fade_out + '_box'].beginElement();
	faders['fade_out_' + fade_out + '_text'].beginElement();
}
function move_heading_to_front(currency) {
	//appendchild first removes then appends the element
	headings_container.appendChild(currency_headings[currency]);
}
function change_currency_state(new_currency) {
	move_heading_to_front(new_currency);
	switch(new_currency) {
		case 'btc':
			switch(svg_heading_positions) {
				case 'btc,local,satoshis': //swap btc and local headings
					fade_heading_in_out('btc', 'local');
					move_heading_horizontal(btc_heading_animate, 0, 60);
					move_heading_horizontal(local_currency_heading_animate, 60, 0);
					svg_heading_positions = 'local,btc,satoshis';
					break;
				case 'btc,satoshis,local': //swap btc and satoshis headings
					fade_heading_in_out('btc', 'satoshis');
					move_heading_horizontal(btc_heading_animate, 0, 100);
					move_heading_horizontal(satoshis_heading_animate, 60, 0);
					svg_heading_positions = 'satoshis,btc,local';
					break;
				case 'local,btc,satoshis': //btc already in the center
					break;
				case 'local,satoshis,btc': //swap btc and satoshis headings
					fade_heading_in_out('btc', 'satoshis');
					move_heading_horizontal(btc_heading_animate, 160, 60);
					move_heading_horizontal(satoshis_heading_animate, 60, 120);
					svg_heading_positions = 'local,btc,satoshis';
					break;
				case 'satoshis,local,btc': //swap btc and local headings
					fade_heading_in_out('btc', 'local');
					move_heading_horizontal(btc_heading_animate, 160, 100);
					move_heading_horizontal(local_currency_heading_animate, 100, 160);
					svg_heading_positions = 'satoshis,btc,local';
					break;
				case 'satoshis,btc,local': //btc already at the center
					break;
			}
			break;
		case 'satoshis':
			switch(svg_heading_positions) {
				case 'btc,local,satoshis': //swap satoshis and local headings
					fade_heading_in_out('satoshis', 'local');
					move_heading_horizontal(satoshis_heading_animate, 120, 60);
					move_heading_horizontal(local_currency_heading_animate, 60, 160);
					svg_heading_positions = 'btc,satoshis,local';
					break;
				case 'btc,satoshis,local': //satoshis already at the center
					break;
				case 'local,btc,satoshis': //swap satoshis and btc headings
					fade_heading_in_out('satoshis', 'btc');
					move_heading_horizontal(satoshis_heading_animate, 120, 60);
					move_heading_horizontal(btc_heading_animate, 60, 160);
					svg_heading_positions = 'local,satoshis,btc';
					break;
				case 'local,satoshis,btc': //satoshis already at the center
					break;
				case 'satoshis,local,btc': //swap satoshis and local headings
					fade_heading_in_out('satoshis', 'local');
					move_heading_horizontal(satoshis_heading_animate, 0, 60);
					move_heading_horizontal(local_currency_heading_animate, 100, 0);
					svg_heading_positions = 'local,satoshis,btc';
					break;
				case 'satoshis,btc,local': //swap satoshis and btc headings
					fade_heading_in_out('satoshis', 'btc');
					move_heading_horizontal(satoshis_heading_animate, 0, 60);
					move_heading_horizontal(btc_heading_animate, 100, 0);
					svg_heading_positions = 'btc,satoshis,local';
					break;
			}
			break;
		case 'local-currency':
			switch(svg_heading_positions) {
				case 'btc,local,satoshis': //local currency already at the center
					break;
				case 'btc,satoshis,local': //swap local currency and satoshis
					fade_heading_in_out('local', 'satoshis');
					move_heading_horizontal(local_currency_heading_animate, 160, 60);
					move_heading_horizontal(satoshis_heading_animate, 60, 120);
					svg_heading_positions = 'btc,local,satoshis';
					break;
				case 'local,btc,satoshis': //swap local currency and btc headings
					fade_heading_in_out('local', 'btc');
					move_heading_horizontal(local_currency_heading_animate, 0, 60);
					move_heading_horizontal(btc_heading_animate, 60, 0);
					svg_heading_positions = 'btc,local,satoshis';
					break;
				case 'local,satoshis,btc': //swap local currency and satoshis
					fade_heading_in_out('local', 'satoshis');
					move_heading_horizontal(local_currency_heading_animate, 0, 100);
					move_heading_horizontal(satoshis_heading_animate, 60, 0);
					svg_heading_positions = 'satoshis,local,btc';
					break;
				case 'satoshis,local,btc': //local currency already at the center
					break;
				case 'satoshis,btc,local': //swap local and btc headings
					fade_heading_in_out('local', 'btc');
					move_heading_horizontal(local_currency_heading_animate, 160, 100);
					move_heading_horizontal(btc_heading_animate, 100, 160);
					svg_heading_positions = 'satoshis,local,btc';
					break;
			}
			break;
	}
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
		var svg_y = svg_y_size * (balance_json[i][1]['sat'] - y_range['min']['sat']) / y_abs;
		svg_dims[i] = [svg_x, svg_y];
	}
	return svg_dims;
}
function update_poly(poly_num, poly_points_str) {
	var poly = svgdoc.getElementById('poly' + poly_num);
	poly.setAttribute('points', poly_points_str);
}
function clear_axis_dashlines(x_or_y) {
	switch(x_or_y) {
		case 'x':
			var id_str_start = 'vertical-dashline';
			break;
		case 'y':
			var id_str_start = 'horizontal-dashline';
			break;
	}
	//only clear the label for the 0th dashline
	dashline0 = svgdoc.getElementById(id_str_start + 0);
	dashline0.children[0].textContent = "0";

	//delete all but the first dashline and clear all axis labels
	var try_final_i = 10;
	for(i = 1; i < try_final_i; i++) {
		var newelement = svgdoc.getElementById(id_str_start + i);
		if(newelement !== null) {
			svgdoc.removeChild(newelement);
			try_final_i++; //always try 10 beyond the last known element
		}
	}
}
function set_axis_values(x_or_y, lowval, highval, num_divisions) {
	//use 0 <= x <= svg_x_size or 0 <= y <= svg_y_size. beyond this is out of
	//bounds
	var num_dashlines = num_divisions - 1;
	switch(x_or_y) {
		case 'x':
			var id_str_start = 'vertical-dashline';
			var svg_chart_max = svg_x_size;
			var display_value_translated = unixtime2datetime_str(lowval);
			break;
		case 'y':
			var id_str_start = 'horizontal-dashline';
			var svg_chart_max = svg_y_size;
			var display_value_translated = add_currency_commas(one_dp(lowval));
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
				display_value_translated = add_currency_commas(one_dp(display_value));
				break;
		}
		newelement.children[0].textContent = display_value_translated;
	}
}
function one_dp(val) {
	//round number to 1 decimal place
	return Math.round(val * 10) / 10;
}
function add_currency_commas(val) {
	//while i could do this with a single regex:
	//return val.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
	//this is virtually unreadable and hard to debug. far easier to use a simple
	//loop:
	val = val.toString();
	if(val < 1000) return val;
	var dot_position = val.indexOf('.');
	var has_dot = (dot_position > -1);
	var above_dot = val; //default
	var dot_and_beyond = ''; //default
	if(has_dot) {
		above_dot = val.substr(0, dot_position);
		dot_and_beyond = val.substr(dot_position);
	}
	var strlen = above_dot.length;
	var chunks = [];
	var take_length = 3;
	for(var i = 0; i < strlen; i += 3) {
		var start_chunk = strlen - i - 3;
		if(start_chunk < 0) {
			take_length = 3 + start_chunk;
			start_chunk = 0;
		}
		chunks.push(above_dot.substr(start_chunk, take_length));
	}
	return chunks.reverse().join(',') + dot_and_beyond;
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
function get_range(x_or_y, balance_json, num_dashlines) {
	var min = 99999999999999999; //init to the largest conceivable number
	var max = -99999999999999999; //init to the smallest conceivable number
	var currency_min = {'sat': min, 'btc': min, 'local': min};
	var currency_max = {'sat': max, 'btc': max, 'local': max};
	var currencies = ['sat', 'btc', 'local'];
	//find the max and min
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
			max = unixtime_day_start(max) + day_in_seconds;
			var res = divisible_date_below(min, max, num_dashlines);
			return {'min': res['min'], 'max': max, 'unit': res['unit']};
		case 'y':
			for(var j = 0; j < 3; j++) {
				var cur = currencies[j];
				//currency_max[cur] *= 1.1; //10% over max. works because min = 0
				currency_max[cur] = parseFloat(closest_currency_above(currency_max[cur]));
			}
			return {'min': currency_min, 'max': currency_max};
	}
}
function closest_currency_above(val) {
	//given a float currency value, find the closest multiple of 10 above it. ie
	//5.5 -> 6, 27459.63 -> 30000, 123.4 -> 200, 987 -> 1000, 0.00342 -> 0.004,
	//0.98 -> 1 and return a string. you can convert to float if necessary, but
	//string preserves the correct number without inaccuracy.

	val = val.toFixed(20); //no e-234234 notation. max resolution is 20dp

	//get the parts of the number above and below the decimal place
	parts = val.toString().split('.');
	if(val >= 1) {
		//1 = order 0, 13 = order 1, etc
		var order = parts[0].length - 1;
		var leading_num = parseInt(parts[0].charAt(0)) + 1;
		var zeros_str = repeat_chars('0', order)
		return (leading_num.toString() + zeros_str);
	} else {
		//0.x = order 0, 0.0x = order 1, etc
		for(var order = 0; order < parts[1].length; order++) {
			var leading_num_str = parts[1].charAt(order);
			if(leading_num_str != '0') break;
		}
		var add_this = parseFloat('0.' + repeat_chars('0', order) + '1');
		var simple_val = parseFloat('0.' + repeat_chars('0', order) + leading_num_str);
		if(leading_num_str == 9) order--; //avoid 0.010 - return 0.01 instead
		return (simple_val + add_this).toFixed(order + 1);
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
	var hh = d.getHours();
	var mm = d.getHours();
	var ss = d.getHours();
	var hhmmss = (dd === 0 && mm === 0 && ss === 0) ? '' : ' ' + hh + ':' + mm + ':' + ss;
	return d.toISOString().slice(0, 10) + hhmmss;
}
function unixtime_day_start(unixtime) {
	var d = new Date(unixtime * 1000);
	d.setHours(0, 0, 0, 0); //hours, minutes, seconds, milliseconds
	var daystart_unixtime = d.getTime() / 1000;
	//round to nearest 100 (only necessary due to weird javascript floats)
	//return Math.round(daystart_unixtime / 100) * 100;
	return daystart_unixtime;
}
function divisible_date_below(start_unixtime, max_unixtime, divisions) {
	//find the date that is just below the start_unixtime
	var diff = max_unixtime - start_unixtime;
	var new_minimum = max_unixtime; //init
	switch(true) {
		case (diff >= (day_in_seconds * (divisions - 1))):
			var unit = 'days';
			var period = day_in_seconds;
			break;
		case (diff >= (3600 * (divisions - 1))):
			unit = 'hours';
			var period = 3600;
			break;
		case (diff >= (60 * (divisions - 1))):
			var unit = 'minutes';
			var period = 60;
			break;
	}
	//subtract until the new minimum moves below the start
	while(true) {
		if(new_minimum <= start_unixtime) break;
		new_minimum -= (period * divisions);
	}
	return {'unit': unit, 'min': new_minimum};
}
function repeat_chars(chars, num_repetitions) {
	return Array(num_repetitions + 1).join(chars);
}
