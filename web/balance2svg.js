var day_in_seconds = 24 * 60 * 60;
var all_currencies_zero = {'satoshis': 0, 'btc': 0, 'local-currency': 0};
var svg_x_size = 800;
var svg_y_size = 300;
var num_x_divisions = 5; //the number of spaces between dates on the x-axis
var num_y_divisions = 5; //the number of spaces between values on the y-axis
var done_init = false;
function init() {
	svgdoc = document.getElementById('chart-frame').contentDocument;
	graph_area = svgdoc.getElementById('graph-area'); //used later
	//setup the click events on the heading
	setup_heading_click_events();
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

	x_range = get_range('x', balance_json, num_x_divisions); //global
	set_axis_values('x', x_range, num_x_divisions);

	y_range = get_range('y', balance_json, num_y_divisions); //global
	y_range['unit'] = 'satoshis'; //init to satoshis
	set_axis_values('y', y_range, num_y_divisions);

	var svg_dims = balance_json2svg_dims(balance_json, x_range, y_range);
	var poly_points_str = svg_dims2poly_points_str(svg_dims);
	update_poly(0, poly_points_str);

	var tttarget = svgdoc.getElementById('tttarget');
	tttarget.setAttribute('cx', 100);

	trigger_currency('satoshis'); //init
}
function setup_heading_click_events() {
	//init globals so they are accessible for click events and state changes
	svg_heading_positions = 'btc,satoshis,local-currency';
	btc_heading_animate = svgdoc.getElementById('btc-heading-animate');
	satoshis_heading_animate = svgdoc.getElementById('satoshis-heading-animate');
	local_currency_heading_animate = svgdoc.getElementById('local-currency-heading-animate');
	trigger_currency = function(currency) { //global function expression
		change_currency_state(currency);
		y_range['unit'] = currency;
		set_axis_values('y', y_range, num_y_divisions);
	};
	svgdoc.getElementById('btc-heading').onclick = function() {
		trigger_currency('btc');
	}
	svgdoc.getElementById('satoshis-heading').onclick = function() {
		trigger_currency('satoshis');
	}
	svgdoc.getElementById('local-currency-heading').onclick = function() {	
		trigger_currency('local-currency');
	}
}
function move_heading_horizontal(animation_element, from, to) {
	animation_element.setAttribute('from', from + ',0');
	animation_element.setAttribute('to', to + ',0');
	animation_element.beginElement();
}
function fade_heading_in_out(fade_in, fade_out) {
	svgdoc.getElementById('fade-in-' + fade_in + '-box').beginElement();
	svgdoc.getElementById('fade-in-' + fade_in + '-text').beginElement();
	svgdoc.getElementById('fade-out-' + fade_out + '-box').beginElement();
	svgdoc.getElementById('fade-out-' + fade_out + '-text').beginElement();
}
function move_heading_to_front(currency) {
	//appendchild first removes then appends the element
	svgdoc.getElementById('headings-container').appendChild(svgdoc.getElementById(currency + '-heading'));
}
function focus_currency(currency) {
	for (var currency_i in all_currencies_zero) {
		if(!all_currencies_zero.hasOwnProperty(currency_i)) continue;
		if(currency_i == currency) {
			svgdoc.getElementById('fade-in-' + currency + '-box').beginElement();
			svgdoc.getElementById('fade-in-' + currency + '-text').beginElement();
		} else {
			svgdoc.getElementById('fade-out-' + currency_i + '-box').beginElement();
			svgdoc.getElementById('fade-out-' + currency_i + '-text').beginElement();
		}
	}
}
function change_currency_state(new_currency) {
	move_heading_to_front(new_currency);
	switch(new_currency) {
		case 'btc':
			switch(svg_heading_positions) {
				case 'btc,local-currency,satoshis': //swap btc and local headings
					fade_heading_in_out('btc', 'local-currency');
					move_heading_horizontal(btc_heading_animate, 0, 60);
					move_heading_horizontal(local_currency_heading_animate, 60, 0);
					svg_heading_positions = 'local-currency,btc,satoshis';
					break;
				case 'btc,satoshis,local-currency': //swap btc and satoshis headings
					fade_heading_in_out('btc', 'satoshis');
					move_heading_horizontal(btc_heading_animate, 0, 100);
					move_heading_horizontal(satoshis_heading_animate, 60, 0);
					svg_heading_positions = 'satoshis,btc,local-currency';
					break;
				case 'local-currency,btc,satoshis': //btc already in the center
					break;
				case 'local-currency,satoshis,btc': //swap btc and satoshis headings
					fade_heading_in_out('btc', 'satoshis');
					move_heading_horizontal(btc_heading_animate, 160, 60);
					move_heading_horizontal(satoshis_heading_animate, 60, 120);
					svg_heading_positions = 'local-currency,btc,satoshis';
					break;
				case 'satoshis,local-currency,btc': //swap btc and local headings
					fade_heading_in_out('btc', 'local-currency');
					move_heading_horizontal(btc_heading_animate, 160, 100);
					move_heading_horizontal(local_currency_heading_animate, 100, 160);
					svg_heading_positions = 'satoshis,btc,local-currency';
					break;
				case 'satoshis,btc,local-currency': //btc already at the center
					break;
			}
			break;
		case 'satoshis':
			switch(svg_heading_positions) {
				case 'btc,local-currency,satoshis': //swap satoshis and local headings
					fade_heading_in_out('satoshis', 'local-currency');
					move_heading_horizontal(satoshis_heading_animate, 120, 60);
					move_heading_horizontal(local_currency_heading_animate, 60, 160);
					svg_heading_positions = 'btc,satoshis,local-currency';
					break;
				case 'btc,satoshis,local-currency': //satoshis already at the center
					break;
				case 'local-currency,btc,satoshis': //swap satoshis and btc headings
					fade_heading_in_out('satoshis', 'btc');
					move_heading_horizontal(satoshis_heading_animate, 120, 60);
					move_heading_horizontal(btc_heading_animate, 60, 160);
					svg_heading_positions = 'local-currency,satoshis,btc';
					break;
				case 'local-currency,satoshis,btc': //satoshis already at the center
					break;
				case 'satoshis,local-currency,btc': //swap satoshis and local headings
					fade_heading_in_out('satoshis', 'local-currency');
					move_heading_horizontal(satoshis_heading_animate, 0, 60);
					move_heading_horizontal(local_currency_heading_animate, 100, 0);
					svg_heading_positions = 'local-currency,satoshis,btc';
					break;
				case 'satoshis,btc,local-currency': //swap satoshis and btc headings
					fade_heading_in_out('satoshis', 'btc');
					move_heading_horizontal(satoshis_heading_animate, 0, 60);
					move_heading_horizontal(btc_heading_animate, 100, 0);
					svg_heading_positions = 'btc,satoshis,local-currency';
					break;
			}
			break;
		case 'local-currency':
			switch(svg_heading_positions) {
				case 'btc,local-currency,satoshis': //local currency already at the center
					break;
				case 'btc,satoshis,local-currency': //swap local currency and satoshis
					fade_heading_in_out('local-currency', 'satoshis');
					move_heading_horizontal(local_currency_heading_animate, 160, 60);
					move_heading_horizontal(satoshis_heading_animate, 60, 120);
					svg_heading_positions = 'btc,local-currency,satoshis';
					break;
				case 'local-currency,btc,satoshis': //swap local currency and btc headings
					fade_heading_in_out('local-currency', 'btc');
					move_heading_horizontal(local_currency_heading_animate, 0, 60);
					move_heading_horizontal(btc_heading_animate, 60, 0);
					svg_heading_positions = 'btc,local-currency,satoshis';
					break;
				case 'local-currency,satoshis,btc': //swap local currency and satoshis
					fade_heading_in_out('local-currency', 'satoshis');
					move_heading_horizontal(local_currency_heading_animate, 0, 100);
					move_heading_horizontal(satoshis_heading_animate, 60, 0);
					svg_heading_positions = 'satoshis,local-currency,btc';
					break;
				case 'satoshis,local-currency,btc': //local currency already at the center
					break;
				case 'satoshis,btc,local-currency': //swap local and btc headings
					fade_heading_in_out('local-currency', 'btc');
					move_heading_horizontal(local_currency_heading_animate, 160, 100);
					move_heading_horizontal(btc_heading_animate, 100, 160);
					svg_heading_positions = 'satoshis,local-currency,btc';
					break;
			}
			break;
	}
	//this is not redundant - it is used during initialization
	focus_currency(new_currency);
}
function balance_rel2abs(balance_json) {
	var satoshis = 0; //init
	var btc = 0; //init
	var local_currency = 0; //init
	for(var i = 0; i < balance_json.length; i++) {
		var change_in_satoshis = balance_json[i][1]['satoshis'];
		var change_in_btc = balance_json[i][1]['btc'];
		var change_in_local_currency = balance_json[i][1]['local-currency'];
		satoshis += change_in_satoshis;
		btc += change_in_btc;
		local_currency += change_in_local_currency;
		balance_json[i][1]['satoshis'] = satoshis;
		balance_json[i][1]['btc'] = btc;
		balance_json[i][1]['local-currency'] = local_currency;
	}
	return balance_json;
}
function balance_json2svg_dims(balance_json, x_range, y_range) {
	var svg_dims = [];
	var x_abs = x_range['max'] - x_range['min'];
	var y_abs = y_range['max']['satoshis'] - y_range['min']['satoshis'];
	for(var i = 0; i < balance_json.length; i++) {
		var svg_x = svg_x_size * (balance_json[i][0] - x_range['min']) / x_abs;
		var svg_y = svg_y_size * (balance_json[i][1]['satoshis'] - y_range['min']['satoshis']) / y_abs;
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
function set_axis_values(x_or_y, range_data, num_divisions) {
	//use 0 <= x <= svg_x_size or 0 <= y <= svg_y_size. beyond this is out of
	//bounds
	var num_dashlines = num_divisions - 1;
	var units = range_data['unit'];
	switch(x_or_y) {
		case 'x':
			var lowval = range_data['min'];
			var highval = range_data['max'];
			var id_str_start = 'vertical-dashline';
			var svg_chart_max = svg_x_size;
			var display_value_translated = unixtime2datetime_str(lowval, units, 0);
			var previous_value = lowval;
			break;
		case 'y':
			var lowval = range_data['min'][units];
			var highval = range_data['max'][units];
			var id_str_start = 'horizontal-dashline';
			var svg_chart_max = svg_y_size;
			var display_value_translated = correct_dp(lowval);
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
			newelement.children[0].textContent = ''; //init
			graph_area.appendChild(newelement);
		}
		newelement = set_id(newelement, this_id_str);
		switch(x_or_y) {
			case 'x':
				position_absolutely(newelement, position, null);
				display_value_translated = unixtime2datetime_str(display_value, units, previous_value);
				previous_value = display_value;
				break;
			case 'y':
				position_absolutely(newelement, null, position);
				display_value_translated = correct_dp(display_value);
				break;
		}
		newelement.children[0].textContent = display_value_translated;
	}
}
function correct_dp(val) {
	//get rid of decimal places if the number is over a million, else round
	//number to 1 decimal place
	switch(true) {
		case (val == 0):
			return val;
		case (val >= 1000000):
			return billion_trillion_etc(val.toFixed()); //0dp
		case(val < 1):
			//this works because we chop off the trailing 0's in add_currency_delimiters()
			return add_currency_delimiters(val.toFixed(9)); //9dp
		default:
			return add_currency_delimiters(val.toFixed(1)); //1dp
	}
}
function billion_trillion_etc(val) {
	//take a number over 1000000 and convert to 'million', 'billion', etc
	if(val >= 1000000000000000000) return (val / 1000000000000000000) + ' quintillion';
	if(val >= 1000000000000000)    return (val / 1000000000000000) + ' quadrillion';
	if(val >= 1000000000000)       return (val / 1000000000000) + ' trillion';
	if(val >= 1000000000)          return (val / 1000000000) + ' billion';
	if(val >= 1000000)             return (val / 1000000) + ' million';
}
function add_currency_delimiters(val) {
	//both above and below the  decimal point, thanks to
	var delimiter = ' ';
	//regex thanks to http://stackoverflow.com/a/2901298
	var re = new RegExp('\\B(?=(\\d{3})+(?!\\d))', 'g');
	var val_str = val.toString();
	if(val_str.indexOf('.') == -1) return val_str.replace(re, delimiter);
	var parts = val.toString().split('.');
	parts[0] = parts[0].replace(re, delimiter);
	if(parseInt(parts[1]) == 0) return parts[0];
	//chop off chunks of '000' from the right
	parts[1] = parts[1].replace(/(000)+$/, '');
	parts[1] = parts[1].replace(re, delimiter);
	return parts.join('.').replace(/0+$/, ''); //chop off straggling 0's
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
	var currency_min = {'satoshis': min, 'btc': min, 'local-currency': min};
	var currency_max = {'satoshis': max, 'btc': max, 'local-currency': max};
	var currencies = ['satoshis', 'btc', 'local-currency'];
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
			var units = get_date_units(max, min, num_dashlines);
			max = next_unit(max, units);
			var min = divisible_date_below(min, max, num_dashlines, units);
			return {'min': min, 'max': max, 'unit': units};
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
var months = {
	0: 'Jan', 1: 'Feb', 2: 'Mar', 3: 'Apr', 4: 'May', 5: 'Jun', 6: 'Jul',
	7: 'Aug', 8: 'Sep', 9: 'Oct', 10: 'Nov', 11: 'Dec'
}
function unixtime2datetime_str(unixtime, units, previous_unixtime) {
	//the rules in this function are intended to present as nice a date for the
	//user as possible. its easier just to read the code than explain all the
	//rules here
	var d = new Date(unixtime * 1000);
	var date_part = d.getDate() + '-' + months[d.getMonth()] + '-' + d.getFullYear();
	if(units == 'days') return date_part;

	//from now on we are dealing with x-hourly or x-minutely increments

	var h = d.getHours();
	var m = d.getMinutes();
	var d_prev = new Date(previous_unixtime * 1000);
	var h_prev = d_prev.getHours();
	var m_prev = d_prev.getMinutes();
	var date_part_prev = d_prev.getDate() + '-' + months[d_prev.getMonth()] + '-' + d_prev.getFullYear();

	if(date_part == date_part_prev) date_part = '';
	else date_part = ', ' + date_part; //the time comes before the date

	//we always want to say the hours, because 'x minutes' alone makes no sense
	switch(units) {
		case 'hours':
			if(h == 0) h = 'midnight';
			else if(h == 12) h = 'mid-day';
			else {
				var ampm = (h >= 12) ? 'pm' : 'am';
				h = h % 12;
				h += ampm;
			}
			return h + date_part;
		case 'minutes':
			return add_zero(h) + ':' + add_zero(m) + date_part;
	}
}
function next_unit(unixtime, unit) {
	//chop to the current 'unit' then add the length of that unit on
	//eg for 'days': chop to midnight on the current day then add a day
	var d = new Date(unixtime * 1000);
	switch(unit) {
		case 'days':
			d.setHours(0, 0, 0, 0); //hours, minutes, seconds, milliseconds
			var daystart_unixtime = d.getTime() / 1000;
			return daystart_unixtime + day_in_seconds;
		case 'hours':
			d.setMinutes(0, 0, 0); //minutes, seconds, milliseconds
			var hourstart_unixtime = d.getTime() / 1000;
			return hourstart_unixtime + 3600;
		case 'minutes':
			d.setSeconds(0, 0); //seconds, milliseconds
			var minutestart_unixtime = d.getTime() / 1000;
			return minutestart_unixtime + 60;
	}
}
function add_zero(val) {
	//getHours(), getMinutes() and getSeconds() don't add leading zeros
	return (val < 10) ? "0" + val : val.toString();
}
function get_date_units(max_unixtime, min_unixtime, divisions) {
	//do the max and the min dates span days, hours or minutes?
	var diff = max_unixtime - min_unixtime;
	switch(true) {
		case (diff < (3 * 3600))://day_in_seconds / 2)):
			return 'minutes';
		case (diff >= (day_in_seconds * 3)):
		//case (diff >= (day_in_seconds * (divisions - 1))):
			return 'days';
		default: //case (diff < (3600 * (divisions - 1))):
			return 'hours';
	}
}
function divisible_date_below(start_unixtime, max_unixtime, divisions, units) {
	//find the date that is just below the start_unixtime
	var diff = max_unixtime - start_unixtime;
	var new_minimum = max_unixtime; //init
	switch(units) {
		case 'days':
			var subtract = day_in_seconds * divisions;
			break;
		case 'hours':
			var subtract = 3600 * divisions;
			break;
		case 'minutes':
			var subtract = 60 * 10 * divisions; //advance in blocks of 10 mins * divisions
			break;
	}
	//subtract until the new minimum moves below the start
	while(true) {
		if(new_minimum <= start_unixtime) break; //more readable
		new_minimum -= subtract;
	}
	return new_minimum;
}
function repeat_chars(chars, num_repetitions) {
	return Array(num_repetitions + 1).join(chars);
}
