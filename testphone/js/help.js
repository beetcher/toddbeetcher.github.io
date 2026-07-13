const help = (() => {
  const ICON_GLOSSARY_ITEMS = [
    { bold: 'Settings gear',         text: '— opens Routing Configuration' },
    { bold: 'Download',              text: '— exports your current conversation' },
    { bold: 'Reset',                 text: '— archives the current conversation and starts a new one' },
    { bold: 'Help (?)',              text: '— opens what you\'re reading now' },
    { bold: 'Panel toggle',          text: '— hides or shows the developer controls on the right' },
    { bold: 'Phone number field icon', text: '— opens a dropdown of previously used numbers for that field' },
  ];

  const CONTENT = {
    overview: {
      title: 'Overview',
      body: 'Test Phone is a local development tool that stands in for Twilio. It lets you build and test SMS-driven applications — like Commander, Recordari, and Channel 19 — without a real Twilio account, phone number, or cellular connection. A small background service called the Router stands in for Twilio: it receives your messages and forwards them to the application\'s webhook (the URL an application listens on to receive incoming texts), then delivers that application\'s replies back to this phone — exactly like a live text conversation would.',
    },
    groups: [
      {
        name: 'Getting Started',
        topics: [
          {
            id: 'try-it-now',
            title: 'Try It Now — Reference Apps',
            body: 'Three numbers work immediately with no setup: +15550000001 (Echo, which repeats back whatever you send), +15550000002 (Random Response), and +15550000003 (Random Joke). Enter a My Phone Number, set one of these as your destination, and send a message to see the whole system work end to end.',
          },
          {
            id: 'starting-a-conversation',
            title: 'Starting a Conversation',
            body: '“My Phone Number” is the virtual phone you’re using — each number keeps its own separate, saved conversation history. “Destination Phone Number” is who you’re texting. Conversations survive page refreshes and browser restarts, so reopening a phone number brings your history right back, just like a real device.',
          },
          {
            id: 'sending-and-receiving',
            title: 'Sending and Receiving Messages',
            body: 'Type a message and send it like a normal text. Replies don’t arrive instantly — this phone checks for new messages once per second, so there’s a brief, realistic delay before a response appears.',
          },
        ],
      },
      {
        name: 'Configuration',
        topics: [
          {
            id: 'routing-configuration',
            title: 'Routing Configuration',
            body: 'Click the settings gear to open Routing Configuration. Here you tell the Router which application should receive messages sent to a given fake Twilio number, by entering that application’s webhook URL — the address it listens on for incoming texts. The optional App Name field labels that entry — it shows up at the top of the phone screen during a conversation and in downloaded conversation exports, so you always know which app you’re talking to.',
          },
          {
            id: 'icon-glossary',
            title: 'Icon Glossary',
            isList: true,
          },
        ],
      },
      {
        name: 'Managing Conversations',
        topics: [
          {
            id: 'downloading',
            title: 'Downloading a Conversation',
            body: 'The download button saves your currently active conversation as a file — sender, recipient, message text, timestamps, and the resolved application name for each message. If the Router can’t be reached at download time, the export still completes, using raw phone numbers in place of app names.',
          },
          {
            id: 'resetting',
            title: 'Resetting a Conversation',
            body: 'Reset starts a new, empty conversation for the current phone number. Nothing is ever deleted — your previous conversation is archived automatically rather than erased. Reset only affects visible message history; your phone numbers, routing configuration, and other settings are untouched.',
          },
          {
            id: 'phone-number-history',
            title: 'Phone Number History',
            body: 'Both phone number fields remember numbers you’ve used before. Click the small icon next to either field to pick from recent numbers instead of retyping them — or just type a new one, which gets added to history automatically.',
          },
          {
            id: 'multiple-tabs',
            title: 'Working Across Multiple Tabs',
            body: 'If you have Test Phone open in more than one browser tab or window, “last used” phone numbers are shared between all of them rather than tracked separately per tab — they’re stored by your browser as one shared set, not one per tab. Changing a number in one tab means the next fresh load of another tab will show that same number. This is expected, not a bug.',
          },
        ],
      },
      {
        name: 'Reference',
        topics: [
          {
            id: 'keyboard-shortcuts',
            title: 'Keyboard Shortcuts',
            body: 'Press Ctrl+Shift+C (Cmd+Shift+C on Mac) to open Routing Configuration directly, without clicking the gear icon. Inside that modal, Enter moves you through each row’s fields in order, and Escape closes the modal — if you have unsaved changes, you’ll be asked to confirm before they’re discarded.',
          },
          {
            id: 'common-errors',
            title: 'Common Errors',
            body: '“No routing entry for [number]” means that destination isn’t configured yet — open Routing Configuration and add it. “Type a message first” means you tried to send an empty message. If a download seems to be missing application names, the background Router service may have been temporarily unreachable when you clicked download — your conversation itself is never affected either way.',
          },
          {
            id: 'collapsing-panel',
            title: 'Collapsing the Panel',
            body: 'Click the panel toggle to hide the developer controls on the right side of the screen, giving the phone more room. The toggle stays visible so you can bring the panel back anytime — your preference is remembered the next time you open Test Phone.',
          },
        ],
      },
    ],
  };

  let modalEl, boxEl, bodyEl, titleEl, closeBtnEl;

  function _findTopic(id) {
    for (const group of CONTENT.groups) {
      const topic = group.topics.find(t => t.id === id);
      if (topic) return topic;
    }
    return null;
  }

  function _renderIndex() {
    titleEl.textContent = 'Help';
    bodyEl.innerHTML = '';

    const overviewItem = document.createElement('div');
    overviewItem.className = 'help-topic-item';
    overviewItem.textContent = CONTENT.overview.title;
    overviewItem.addEventListener('click', () => _renderBlurb('overview'));
    bodyEl.appendChild(overviewItem);

    for (const group of CONTENT.groups) {
      const groupEl = document.createElement('div');
      groupEl.className = 'help-group';

      const headerEl = document.createElement('div');
      headerEl.className = 'help-group-header';
      headerEl.textContent = group.name;
      groupEl.appendChild(headerEl);

      for (const topic of group.topics) {
        const topicEl = document.createElement('div');
        topicEl.className = 'help-topic-item';
        topicEl.textContent = topic.title;
        topicEl.addEventListener('click', () => _renderBlurb(topic.id));
        groupEl.appendChild(topicEl);
      }

      bodyEl.appendChild(groupEl);
    }
  }

  function _renderBlurb(id) {
    let title;
    if (id === 'overview') {
      title = CONTENT.overview.title;
    } else {
      const topic = _findTopic(id);
      if (!topic) { _renderIndex(); return; }
      title = topic.title;
    }

    titleEl.textContent = title;
    bodyEl.innerHTML = '';

    const backBtn = document.createElement('button');
    backBtn.className = 'help-back-btn';
    backBtn.textContent = '← Back';
    backBtn.addEventListener('click', _renderIndex);
    bodyEl.appendChild(backBtn);

    if (id === 'icon-glossary') {
      const intro = document.createElement('p');
      intro.className = 'help-blurb-text';
      intro.textContent = 'Quick reference for every icon on screen:';
      bodyEl.appendChild(intro);

      const ul = document.createElement('ul');
      ul.className = 'help-icon-list';
      for (const item of ICON_GLOSSARY_ITEMS) {
        const li = document.createElement('li');
        const strong = document.createElement('strong');
        strong.textContent = item.bold;
        li.appendChild(strong);
        li.appendChild(document.createTextNode(' ' + item.text));
        ul.appendChild(li);
      }
      bodyEl.appendChild(ul);
    } else {
      const body = id === 'overview' ? CONTENT.overview.body : _findTopic(id).body;
      const p = document.createElement('p');
      p.className = 'help-blurb-text';
      p.textContent = body;
      bodyEl.appendChild(p);
    }
  }

  function init() {
    const overlay = document.createElement('div');
    overlay.id = 'help-modal';
    overlay.className = 'modal-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Help');
    overlay.innerHTML =
      '<div class="modal-box help-modal-box" tabindex="-1">' +
        '<div class="modal-header">' +
          '<span id="help-modal-title" class="modal-title">Help</span>' +
          '<button id="help-modal-close" class="modal-close-btn" aria-label="Close">&times;</button>' +
        '</div>' +
        '<div id="help-modal-body" class="modal-body help-modal-body"></div>' +
      '</div>';
    document.body.appendChild(overlay);

    modalEl    = overlay;
    boxEl      = overlay.querySelector('.help-modal-box');
    bodyEl     = document.getElementById('help-modal-body');
    titleEl    = document.getElementById('help-modal-title');
    closeBtnEl = document.getElementById('help-modal-close');

    closeBtnEl.addEventListener('click', close);
    modalEl.addEventListener('click', (e) => { if (e.target === modalEl) close(); });
    modalEl.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
    });
  }

  function open() {
    _renderIndex();
    modalEl.classList.add('open');
    boxEl.focus();
  }

  function close() {
    modalEl.classList.remove('open');
  }

  return { init, open, close };
})();
