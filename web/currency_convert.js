function balance_currency_convert(satoshis_json, exchange_rate) {
	//convert a json list of the format [[time, satoshis], [time, satoshis]]
	//to the format [time, {'btc': 123, 'sat': 321, 'local': 2}]
	var balance_json = [];
	for(var i = 0; i < satoshis_json.length; i++) {
		var satoshis_i = satoshis_json[i][1];
		balance_json[i] = [satoshis_json[i][0], {
			'satoshis': satoshis_i,
			'btc': satoshis_i / 100000000,
			'local-currency': satoshis_i * exchange_rate / 100000000
		}];
	}
	return balance_json;
}
