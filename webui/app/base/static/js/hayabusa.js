var HayabusaChartColors = [
  ['rgb(75, 192, 192)', 'rgba(75, 192, 192, 0.5)'],
  ['rgb(54, 162, 235)', 'rgba(54, 162, 235, 0.5)'],
  ['rgb(153, 102, 255)','rgba(153, 102, 255, 0.5)'],
  ['rgb(255, 206, 86)', 'rgba(255, 206, 86, 0.5)'],
  ['rgb(255, 99, 132)', 'rgba(255, 99, 132, 0.5)'],
  ['rgb(255, 159, 64)', 'rgba(255, 159, 64, 0.5)']];

function updateChartSingleColmn() {
  updateChartColmun(12)
}

function updateChartTwoColmn() {
  updateChartColmun(6)
}

function updateChartThreeColmn() {
  updateChartColmun(4)
}

function updateChartColmun(num) {
  var newClass = 'col-md-' + num + ' col-sm-'+ num + ' col-xs-' + num;
  $('[id^=chart_block_]').attr('class', newClass);
}

function updateTimeUnit(chart, unit) {
  chart.options.scales.xAxes[0].time.unit = unit;
  chart.update();
}

function timeUnitMinute(chart) {
  updateTimeUnit(chart, 'minute');
}

function timeUnitHour(chart) {
  updateTimeUnit(chart, 'hour');
}

function timeUnitDay(chart) {
  updateTimeUnit(chart, 'day');
}

function timeUnitWeek(chart) {
  updateTimeUnit(chart, 'week');
}

function timeUnitMonth(chart) {
  updateTimeUnit(chart, 'month');
}

function clearChart(chart) {
  chart.data.datasets = [];
  chart.update();
}

function createChart(queryId) {
  var ctx = document.getElementById(queryId).getContext('2d');
  var chart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: []
    },
    options: {
      scales: {
        xAxes: [{
          type: 'time',
          ticks: {
            autoSkip: true,
            maxTicksLimit: 20
          },
          time: {
            unit: 'minute',
            displayFormats: {
              minute: 'HH:mm',
              hour: 'HH:mm',
              day: 'YYYY/MM/DD',
              week: 'YYYY/MM/DD',
              month: 'YYYY/MM/DD'
            }
          },
          distribution: 'linear'
        }]
      }
    }
  });
  return chart;
}

function updateChartDataset(queryId, data, chart, index, color) {
  if (chart.data.datasets[index] === undefined) {
    chart.data.datasets.push({fill: false, lineTension: 0,
      label: data[queryId]['meta']['name'],
      data: data[queryId]['data'],
      borderColor: color[0],
      backgroundColor: color[1]
    });
  } else {
    chart.data.datasets[index].label = data[queryId]['meta']['name'];
    chart.data.datasets[index].data = data[queryId]['data'];
  }
}

function updateChart(chart, url) {
  $.ajax({
    url: url,
    type: 'get',
    success: function (data, textStatus, jqXHR) {
      var index = 0;
      for (var queryId in data) {
        var color_index = index % HayabusaChartColors.length;
        var color = HayabusaChartColors[color_index];
        updateChartDataset(queryId, data, chart, index, color);
        index++;
      }
      chart.update();
    },
  });
}

function updateCharts(charts, url) {
  $.ajax({
    url: url,
    type: 'get',
    success: function (data, textStatus, jqXHR) {
      var index = 0;
      for (var queryId in data) {
        var chart = charts[queryId];
        var color_index = index % HayabusaChartColors.length;
        var color = HayabusaChartColors[color_index];
        updateChartDataset(queryId, data, chart, 0, color);
        chart.update();
        index++;
      }

    },
  });
}

function createQueryListDataTable(id, url) {
  var table = $(id).DataTable({
    select: true,
    order: [],
    ajax: {
      url: url,
      dataSrc: ''
    },
    aLengthMenu: [ 10, 20],
    columns: [{data: 'name'},{data: 'match'},{data: 'exact'}]
  });
  return table;
}

function createLogSearchDataTable(id, url) {
  var table = $(id).DataTable({
    processing: true,
    serverSide: true,
    searching: false,
    aLengthMenu: [ 25, 50, 100, 200],
    ajax: url
  });
  return table;
}

function saveQuery(form, callback) {
  $.ajax({
    url: form.attr('action'),
    type: 'post',
    data: form.serialize(),
    success: function (data, textStatus, jqXHR) {
      if (data['error']) {
        $('#error').text(data['error']).show();
      } else {
        callback();
      }
    },
  });
}

function deleteQuery(url, callback) {
  $.ajax({
    url: url,
    type: 'delete',
    success: function (data, textStatus, jqXHR) {
      if (data['error']) {
        $('#error').text(data['error']).show();
      } else {
        callback();
      }
    },
  });
}

function createDateRangePicker(id, endDate) {
  $(id).daterangepicker({
    endDate: endDate,
    locale: { format: 'YYYY-MM-DD H:mm'},
    autoApply: true,
    timePicker24Hour: true,
    timePicker: true
  });
}

function loadTable(table, requestId, statusCheckFunc, statusCheckTimer, tableDrawURLBase) {
  table.ajax.url(tableDrawURLBase+requestId).load(function (data){
    var meta_info = data['meta'];
    var status = meta_info['exit_status'];
    if (meta_info['stderr'] != '') {
      $('#error').text(meta_info['stderr']).show();
    }
    $('#result').text('Received Result: '+requestId+', Exit Status: '+status).show();
    clearInterval(statusCheckTimer);
    statusCheckFunc();
  });
}

function searchRequest(table, form, statusCheckTimer, statusCheckURLBase, tableDrawURLBase) {
  $.ajax({
    url: form.attr('action'),
    type: 'post',
    data: form.serialize(),
    success: function (data, textStatus, jqXHR) {
      requestId = data['id'];
      $('#notice').text('Requested: '+requestId).show();
      if (data['error']) {
        $('#error').text(data['error']).show();
      } else {
        var now = moment();
        var checkFunc = function (){ checkStatus(requestId, now, statusCheckTimer, statusCheckURLBase) };
        checkFunc();
        statusCheckTimer = setInterval(checkFunc, 5*1000);
        loadTable(table, requestId, checkFunc, statusCheckTimer, tableDrawURLBase);
      }
    },
  });
}

function timeDiff(startTime) {
    return Math.ceil((moment() - startTime) / 1000.0)
}

function timeToStr(time) {
  var str = '';
  if (time > 60) {
    var min = Math.floor(time / 60.0);
    var sec = time % 60;
    str = min + 'm ' + sec + 's';
  } else {
    str = time + 's';
  }
  return str;
}

function checkStatus(requestId, startTime, statusCheckTimer, statusCheckURLBase) {
  $.ajax({
    url: statusCheckURLBase+requestId,
    type: 'get',
    success: function (data, textStatus, jqXHR) {
      if (data['error']) {
        clearInterval(statusCheckTimer);
        $('#status_error').text('Status Check Error: '+data['error']).show();
      } else {
        var status = data['status'];
        var diff = timeDiff(startTime);
        var timeStr = timeToStr(diff);
        var message = 'Status: ' + status;
        if (data['data']) {
          var cmds = data['data'];
          var num = cmds.length;
          var numCompleted = cmds.filter(function(e){return e !== null && e.indexOf('completed-') == 0}).length;
          var numWaiting = cmds.filter(function(e){return e === null}).length;
          var numRunning = num - numCompleted - numWaiting;
          message += ', completed: ' + numCompleted + '/' + num;
          message += ', running: ' + numRunning + '/' + num;
          message += ', waiting: ' + numWaiting + '/' + num;
        }
        message += ' [elapsed time: '+ timeStr + ']';
        $('#status').text(message).show();
      }
    }
  });
}