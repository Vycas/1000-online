var xmlHttp = createXmlHttpRequestObject();

function getParam(name) {
  var url = location.href;
  var param = url.substr(url.indexOf(name+'=')+name.length+1);
  var amp = param.indexOf('&')
  if (amp >= 0) {
    param = param.substr(0, amp);
  }
  return param;
}

var dict;
var last_turn;
var last_state;

function sendMessage(url) {
  var xmlHttp = createXmlHttpRequestObject();
  
  if (xmlHttp) {
    try {
      xmlHttp.open("POST", url, false);
      xmlHttp.send(null);
    }
    catch(e) {}
  }
}

function update() {
  var url = '/update?id=' + getParam('id');
  
  if (xmlHttp) {
    try {
      xmlHttp.onreadystatechange = function() {
        if ((xmlHttp.readyState == 4) && (xmlHttp.status == 200)) {
          var response = xmlHttp.responseText;
          eval('dict = ' + response);
          document.getElementById('info_header').innerHTML = dict.info_header;
          var myturn = dict.player_turn;
          var turn = dict.player_turn ? 1 : (dict.opponent1_turn ? 2 : 3);
          var players = ['player', 'opponent1', 'opponent2'];
          var properties = ['username', 'points', 'info'];
          for (var i in players) {
            for (var j in properties) {
              document.getElementById(players[i]+'_'+properties[j]).innerHTML = 
                eval('dict.'+players[i]+'_'+properties[j]);
            }
            if (eval('dict.'+players[i]+'_plus')) {
              document.getElementById(players[i]+'_username').innerHTML += ' (+)';
            }
            var e = document.getElementById(players[i]+'_turn');
            e.style.display = eval('dict.'+players[i]+'_turn') ? 'block' : 'none';
          }
          if ((last_turn != turn) || (last_state != dict.state)) {
            last_turn = turn;
            last_state = dict.state;
            document.title = myturn ? '1000 Online - Game (Your turn)' : '1000 Online - Game';
            document.getElementById('trump').innerHTML = '';
            document.getElementById('taken').innerHTML = '';
            var controls = ['deal', 'open', 'blind', 'bettings', 'bet', 'pass', 'plus', 'collect', 'last'];
            for (var i in controls) {
              hide(controls[i]);
            }
            
            switch (dict.state) {
              case 'hosted':
                break;
              case 'ready':
                if (myturn) {
                  show('deal');
                }
                break;
              case 'open_or_blind':
                show('open');
                show('blind');
                break;
              case 'go_blind':
                show('open');
              case 'go_open':
                if (myturn && !dict.passed) {
                  show('bettings');
                  show('bet');
                  if (!dict.first) {
                    show('pass');
                  }
                  add_bets(dict.bettings);
                }
                break;
              case 'collect':
                if (myturn) {
                  show('collect');
                }
                break;
              case 'finalBet':
                if (myturn) {
                  show('bettings');
                  show('bet');
                  add_bets(dict.bettings);
                  if (!dict.player_plus) {
                    show('plus');
                  }
                }
                break;
              case 'inGame':
                show('last');
                document.getElementById('trump').innerHTML = dict.trump;
                document.getElementById('taken').innerHTML = dict.taken;
                break;
              case 'finish':
                break;
            }
          }
          for (var i=1; i<=3; i++) {
            eval("var e=document.getElementById('bank"+i+"'); var v=dict.bank["+(i-1)+"]; "+
                 "if (v) {e.src='/images/cards/'+v+'.gif'; e.style.display='inline';}" + 
                 "else {e.style.display='none'}");
          }
          for (var i=1; i<=10; i++) {
            eval("var e=document.getElementById('card"+i+"'); var v=dict.cards["+(i-1)+"]; "+
                 "if (v) {e.src='/images/cards/'+v+'.gif'; e.style.display='inline';}" + 
                 "else {e.style.display='none'}");
          }
        }
      }
      xmlHttp.open("GET", url, true);
      xmlHttp.send(null);
    }
    catch(e) {
      alert(e.toString());
    }
  }
}

function updater() {
  update();
  window.setTimeout(updater, 3000);
}

function show(element) {
  document.getElementById(element).style.display = 'block';
}

function hide(element) {
  document.getElementById(element).style.display = 'none';
}

function add_bets(bets) {
  if (bets) {
    var bettings = document.getElementById('bettings');
    while (bettings.childNodes.length > 0) {
      bettings.removeChild(bettings.childNodes[0]);
    }
    for (var i=0; i<bets.length; i++) {
      option = document.createElement('option');
      option.setAttribute('value', bets[i])
      option.innerHTML = bets[i];
      bettings.appendChild(option);
    }
  }
}

function put(card) {
  if (!dict.player_turn) {
    return;
  }
  regex = /\/(\w+).gif$/;
  name = card.src.match(regex)[1];
  if (name == 'BACK') {
    return;
  }
  var url = '/put?id=' + getParam('id') + '&card=' + name;
  sendMessage(url);
  update();
  
}

function retrieve(card) {
  if (!(dict.player_turn && dict.state == 'finalBet')) {
    return;
  }
  regex = /\/(\w+).gif$/;
  name = card.src.match(regex)[1];
  if (name == 'BACK') {
    return;
  }
  var url = '/retrieve?id=' + getParam('id') + '&card=' + name;
  sendMessage(url);
  update();
}

function bet() {
  var bettings = document.getElementById('bettings');
  var bet = bettings.options[bettings.selectedIndex].value;
  var url = '/bet?id=' + getParam('id') + '&upto=' + bet;
  sendMessage(url);
  update();
}

function post(cmd, id) {
  var url = '/' + cmd + '?id=' + getParam('id');
  sendMessage(url);
  update();
}

function showLast() {
  if (dict.state == 'inGame') {
    for (var i=1; i<=3; i++) {
      eval("var e=document.getElementById('bank"+i+"'); var v=dict.memo["+(i-1)+"]; "+
           "if (v) {e.src='/images/cards/'+v+'.gif'; e.style.display='inline';}" + 
           "else {e.style.display='none'}");
    }
  }
}

function hideLast() {
  if (dict.state == 'inGame') {
    for (var i=1; i<=3; i++) {
      eval("var e=document.getElementById('bank"+i+"'); var v=dict.bank["+(i-1)+"]; "+
           "if (v) {e.src='/images/cards/'+v+'.gif'; e.style.display='inline';}" + 
           "else {e.style.display='none'}");
    }
  }
}

function quit() {
  location.href = '/sessions'
}