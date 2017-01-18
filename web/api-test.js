function PostJSON(endpoint, dataForServer) {
    var waitForAjax = new $.Deferred();
    for (var k in dataForServer) { // convert each element to string
        if (!dataForServer.hasOwnProperty(k)) continue;
        if (typeof dataForServer[k] !== 'object') continue;
        dataForServer[k] = JSON.stringify(dataForServer[k]);
    }
    $.ajax({
        url: endpoint,
        cache: false,
        type: 'POST',
        waitForAjax: waitForAjax,
        data: JSON.stringify(dataForServer),
        dataType: 'json',
        contentType: 'application/json; charset=utf-8',
        success: function (dataFromServer, textStatus, jqXHR) {
            if (!CheckResponseStatus(dataFromServer, textStatus, jqXHR)) {
                return this.waitForAjax.reject(dataFromServer).promise();
            }
            return this.waitForAjax.resolve(dataFromServer).promise();
        },
        error: CheckResponseStatus
    });
    return waitForAjax.promise();
}

function CheckResponseStatus(dataFromServer, textStatus, jqXHR) {
    if (!dataFromServer.hasOwnProperty('Error') || !dataFromServer.Error.hasOwnProperty('Code')) {
        //we did not receive a response
        Notify('Unable to connect to the server', 'error');
        return false;
    }
    switch (dataFromServer.Error.Code) {
        case 0: // ok :)
            return true;
        case 105: // session token error
            RedirectToLogin();
            break;
        default: // we received a response, but it is an error code
            Notify('<strong>Error ' + dataFromServer.Error.Code + '</strong>: ' + dataFromServer.Error.Status, 'error');
            return false;
    }
}

function Notify(msg, type) {
    alert(msg);
}

$(document).ready(function(){
    $.when(PostJSON('/index')).then(function (dataFromServer) {
        $('#indexEndpointData').val(dataFromServer.Data.Items);
    });

});
