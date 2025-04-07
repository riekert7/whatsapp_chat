import {
  get_time,
  scroll_to_bottom,
  get_messages,
  get_date_from_now,
  is_date_change,
  send_message,
  set_typing,
  is_image,
  get_avatar_html,
} from './chat_utils';

export default class ChatSpace {
  constructor(opts) {
    this.chat_list = opts.chat_list;
    this.$wrapper = opts.$wrapper;
    this.profile = opts.profile;
    this.file = null;
    this.setup();
  }

  setup() {
    this.$chat_space = $(document.createElement('div'));
    this.typing = false;
    this.$chat_space.addClass('chat-space');
    this.setup_header();
    this.messages = [];  // Add this to store messages
    this.fetch_and_setup_messages();
    this.setup_socketio();
  }

  setup_header() {
    this.avatar_html = get_avatar_html(
      this.profile.room_type,
      this.profile.opposite_person_email,
      this.profile.room_name
    );
    const header_html = `
			<div class='chat-header'>
				${
          this.profile.is_admin === true
            ? `<span class='chat-back-button' title='${__('Go Back')}' >
								${frappe.utils.icon('left')}
							</span>`
            : ``
        }
				${this.avatar_html}
				<div class='chat-profile-info'>
					<div class='chat-profile-name'>
					${__(this.profile.room_name)}
					<div class='online-circle'></div>
					</div>
					<div class='chat-profile-status'>${__('Typing...')}</div>
				</div>
			</div>
		`;
    this.$chat_space.append(header_html);
  }

  async fetch_and_setup_messages() {
    try {
      console.log('Fetching messages for:', {
        room: this.profile.room,
        user_email: this.profile.user_email,
        opposite_person_email: this.profile.opposite_person_email,
        profile: this.profile
      });
      
      // Use the mobile number from the profile for fetching messages
      const user_no = this.profile.opposite_person_email || this.profile.user_email;
      console.log('Using user_no for fetching messages:', user_no);
      
      const messages = await get_messages(
        this.profile.room,
        user_no
      );
      console.log('Received messages:', messages);
      
      // Store messages in the component
      this.messages = messages || [];
      
      this.setup_messages(this.messages);
      this.setup_actions();
      this.render();
    } catch (error) {
      console.error('Error fetching messages:', error);
      frappe.msgprint({
        title: __('Error'),
        message: __('Something went wrong. Please refresh and try again.'),
      });
    }
  }

  setup_messages(messages_list) {
    this.$chat_space_container = $(document.createElement('div'));
    this.$chat_space_container.addClass('chat-space-container');

    this.make_messages_html(messages_list);

    this.$chat_space_container.html(this.message_html);
    this.$chat_space.append(this.$chat_space_container);
  }

  make_messages_html(messages_list) {
    this.prevMessage = {};
    this.message_html = ``;
    
    console.log('Processing messages list:', messages_list);
    console.log('Current profile:', this.profile);
    
    if (this.profile.message) {
      messages_list.push(this.profile.message);
      send_message(
        this.profile.message.content,
        this.profile.user,
        this.profile.room,
        this.profile.user_email
      );
    }
    
    messages_list.forEach((element) => {
      console.log('Processing message:', element);
      const date_line_html = this.make_date_line_html(element.creation);
      this.message_html += date_line_html;

      // Default to sender (right side)
      let message_type = 'sender';

      // If it's an incoming message (from others), it should be on the left
      if (element.type === 'Incoming') {
        message_type = 'recipient';
      }
      
      console.log('Message type determined:', message_type);
      
      this.message_html += this.make_message(
        element.content,
        get_time(element.creation),
        message_type,
        element.sender
      ).prop('outerHTML');

      this.prevMessage = element;
    });
    
    console.log('Final message HTML:', this.message_html);
  }

  make_date_line_html(dateObj) {
    let result = `
			<div class='date-line'>
				<span>
					${__(get_date_from_now(dateObj, 'space'))}
				</span>
			</div>
		`;
    if ($.isEmptyObject(this.prevMessage)) {
      return result;
    } else if (is_date_change(dateObj, this.prevMessage.creation)) {
      return result;
    } else {
      return '';
    }
  }

  setup_actions() {
    this.$chat_actions = $(document.createElement('div'));
    this.$chat_actions.addClass('chat-space-actions');
    const chat_actions_html = `
			<span class='open-attach-items'>
				${frappe.utils.icon('attachment', 'lg')}
			</span>
			<input type='file' id='chat-file-uploader'
				accept='image/*, application/pdf, .doc, .docx'
				style='display: none;'
			>
			<input class='form-control type-message'
				type='search'
				placeholder='${__('Type message')}'
			>
			<div>
				<span class='message-send-button'>
					<svg xmlns="http://www.w3.org/2000/svg" width="1.1rem" height="1.1rem" viewBox="0 0 24 24">
						<path d="M24 0l-6 22-8.129-7.239 7.802-8.234-10.458 7.227-7.215-1.754 24-12zm-15 16.668v7.332l3.258-4.431-3.258-2.901z"/>
					</svg>
				</span>
			</div>
		`;
    this.$chat_actions.html(chat_actions_html);
    this.$chat_space.append(this.$chat_actions);
  }

  async handle_upload_file(file) {
    const dataurl = await frappe.dom.file_to_base64(file.file_obj);
    file.dataurl = dataurl;
    file.name = file.file_obj.name;
    return this.upload_file(file);
  }

  upload_file(file) {
    const me = this;
    return new Promise((resolve, reject) => {
      let xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('load', () => {
        resolve();
      });

      xhr.addEventListener('error', () => {
        reject(frappe.throw(__('Internal Server Error')));
      });
      xhr.onreadystatechange = () => {
        if (xhr.readyState == XMLHttpRequest.DONE) {
          if (xhr.status === 200) {
            let r = null;
            let file_doc = null;
            try {
              r = JSON.parse(xhr.responseText);
              if (r.message.doctype === 'File') {
                file_doc = r.message;
              }
            } catch (e) {
              r = xhr.responseText;
            }
            try {
              if (file_doc === null) {
                reject(frappe.throw(__('File upload failed!')));
              }
              me.handle_send_message(file_doc.file_url);
            } catch (error) {
              //pass
            }
          } else {
            try {
              const error = JSON.parse(xhr.responseText);
              const messages = JSON.parse(error._server_messages);
              const errorObj = JSON.parse(messages[0]);
              reject(frappe.throw(__(errorObj.message)));
            } catch (e) {
              // pass
            }
          }
        }
      };

      xhr.open('POST', '/api/method/upload_file', true);
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

      let form_data = new FormData();

      form_data.append('file', file.file_obj, file.name);
      form_data.append('is_private', +false);

      form_data.append('doctype', 'WhatsApp Contact');
      form_data.append('docname', this.profile.room);
      form_data.append('optimize', +true);
      xhr.send(form_data);
    });
  }

  setup_events() {
    const me = this;

    //Timeout function
    me.typing_timeout = () => {
      me.typing = false;
    };

    $('.chat-back-button').on('click', function () {
      me.chat_list.render_messages();
      me.chat_list.render();
    });

    $('.open-attach-items').on('click', function () {
      $('#chat-file-uploader').click();
    });

    $('#chat-file-uploader').on('change', function () {
      if (this.files.length > 0) {
        me.file = {};
        me.file.file_obj = this.files[0];
        me.handle_upload_file(me.file);
        me.file = null;
      }
    });

    $('.message-send-button').on('click', function () {
      me.handle_send_message();
    });

    $('.type-message').keydown(function (e) {
      if (e.which === 13) {
        me.handle_send_message();
      }
    });
  }

  setup_socketio() {
    const me = this;
    console.log('Setting up socket for room:', this.profile.room);
    
    if (frappe.socketio.socket) {
        console.log('Socket object available in chat space setup');
        console.log('Socket connected status in chat space:', frappe.socketio.socket.connected);
    } else {
        console.warn('Socket object not available in chat space setup');
    }
    
    // Handle room-specific messages
    frappe.realtime.on(this.profile.room, function (res) {
        console.log('Socket event received for room:', {
            room: me.profile.room,
            message: res,
            sender: res.sender_user_no,
            current_user: me.profile.user_email,
            type: res.type,
            message_id: res.message_id,
            message_type: res.message_type
        });
        
        // Skip if this is our own outgoing message (we already added it in handle_send_message)
        if (res.sender_user_no === me.profile.user_email && res.type === 'Outgoing') {
            console.log('Skipping own outgoing message:', res.content);
            return;
        }
        
        // Check if message already exists in our messages array using message_id
        const messageExists = me.messages.some(msg => msg.message_id === res.message_id);
        
        if (messageExists) {
            console.log('Message already exists in chat, skipping:', res.content);
            return;
        }
        
        console.log('Adding new message to chat:', res.content);
        
        // Add message to our local messages array
        me.messages.push(res);
        
        // Update UI with the new message
        me.receive_message(res, get_time(res.creation));
        
        // No longer marking as read here - only when user clicks on chat room
    });
    
    // Listen for broadcast updates from other users
    frappe.realtime.on('latest_chat_updates', function(res) {
        console.log('Received latest chat update:', res);
        
        // Only process if this update is for our current room
        if (res.room === me.profile.room) {
            // Skip if this is our own outgoing message
            if (res.sender_user_no === me.profile.user_email && res.type === 'Outgoing') {
                console.log('Skipping broadcast for own outgoing message');
                return;
            }
            
            // Check if message already exists using message_id
            const messageExists = me.messages.some(msg => msg.message_id === res.message_id);
            
            if (messageExists) {
                console.log('Message from broadcast already exists, skipping:', res.content);
                return;
            }
            
            // If we get here, it's a new message from another user
            console.log('Processing new message from another user:', res.content);
            
            // Add to messages array
            me.messages.push(res);
            
            // Update UI
            me.receive_message(res, get_time(res.creation));
            
            // Play notification sound if enabled
            if (frappe.Chat.settings.user.enable_message_tone === 1) {
                frappe.utils.play_sound('chat-message-receive');
            }
        }
    });
    
    console.log('Registered socket listeners for room:', this.profile.room);
  }

  destroy_socket_events() {
    frappe.realtime.off(this.profile.room);
  }

  get_typing_changes(res) {
    if (res.user != this.profile.user_email) {
      if (
        (this.profile.is_admin === true && res.is_guest === 'true') ||
        this.profile.is_admin === false ||
        this.profile.room_type === 'Group' ||
        this.profile.room_type === 'Direct'
      ) {
        if (res.is_typing === 'false') {
          $('.chat-profile-status').css('visibility', 'hidden');
        } else {
          $('.chat-profile-status').css('visibility', 'visible');
          const timeout = setTimeout(() => {
            $('.chat-profile-status').css('visibility', 'hidden');
          }, 3000);
        }
      }
    }
  }

  make_message(content, time, type, name) {
    console.log('Creating message with:', { content, time, type, name });
    
    const message_class = type === 'recipient' ? 'recipient-message' : 'sender-message';
    const $recipient_element = $(document.createElement('div')).addClass(message_class);
    const $message_element = $(document.createElement('div')).addClass('message-bubble');

    const $name_element = $(document.createElement('div'))
      .addClass('message-name')
      .text(name);

    const n = content.lastIndexOf('/');
    const file_name = content.substring(n + 1) || '';
    let $sanitized_content;

    if (content.startsWith('/files/') && file_name !== '') {
      let $url;
      if (is_image(file_name)) {
        $url = $(document.createElement('img'));
        $url.attr({ src: content }).addClass('img-responsive chat-image');
        $message_element.css({ padding: '0px', background: 'inherit' });
        $name_element.css({
          color: 'var(--text-muted)',
          'padding-bottom': 'var(--padding-xs)',
        });
      } else {
        $url = $(document.createElement('a'));
        $url.attr({ href: content, target: '_blank' }).text(__(file_name));

        if (type === 'sender') {
          $url.css('color', 'var(--cyan-100)');
        }
      }
      $sanitized_content = $url;
    } else {
      $sanitized_content = __($('<div>').text(content).html());
    }

    if (type === 'sender' && this.profile.room_type === 'Group') {
      $message_element.append($name_element);
    }
    $message_element.append($sanitized_content);
    $recipient_element.append($message_element);
    $recipient_element.append(`<div class='message-time'>${__(time)}</div>`);

    console.log('Created message element:', $recipient_element.prop('outerHTML'));
    return $recipient_element;
  }

  handle_send_message(attachment) {
    const $type_message = $('.type-message');
    let content = null;

    if (attachment) {
      content = attachment;
    } else {
      content = $type_message.val();
    }

    console.log('Attempting to send message:', {
      content,
      profile: this.profile,
      has_attachment: !!attachment
    });

    if (content.length === 0) {
      console.log('Message content is empty, not sending');
      return;
    }
    this.typing = false;
    if (this.timeout) {
      clearTimeout(this.timeout);
    }

    if (
      this.profile.is_admin === true &&
      frappe.Chat.settings.user.enable_message_tone === 1
    ) {
      frappe.utils.play_sound('chat-message-send');
    }

    // Clear input field immediately
    $type_message.val('');
    
    // Use the mobile number from the profile for sending messages
    const user_no = this.profile.opposite_person_email || this.profile.user_email;
    
    console.log('Sending message with params:', {
      content,
      user: this.profile.user,
      room: this.profile.room,
      user_no,
      attachment
    });
    
    // Send the message
    send_message(
      content,
      this.profile.user,
      this.profile.room,
      user_no,
      attachment
    ).catch((error) => {
      console.error('Error sending message:', error);
      frappe.msgprint({
        title: __('Error'),
        message: __('Failed to send message. Please try again.'),
      });
    });
  }

  receive_message(res, time) {
    console.log('Processing message in receive_message:', {
        content: res.content,
        sender: res.sender_user_no,
        current_user: this.profile.user_email,
        type: res.type,
        message_id: res.message_id,
        message_type: res.message_type
    });
    
    // Don't process if it's our own message (we already added it in handle_send_message)
    if (res.sender_user_no === this.profile.user_email && res.type === 'Outgoing') {
        console.log('Skipping own outgoing message in receive_message:', res.content);
        return;
    }

    if (
        this.profile.is_admin === true &&
        $('.chat-element').is(':visible') &&
        frappe.Chat.settings.user.enable_message_tone === 1
    ) {
        frappe.utils.play_sound('chat-message-receive');
    }

    // Default to recipient (left side)
    let chat_type = 'recipient';
    
    // If it's an outgoing message (from us), it should be on the right
    if (res.type === 'Outgoing') {
        chat_type = 'sender';
    }

    console.log('Adding message to UI:', {
        content: res.content,
        chat_type: chat_type,
        sender: res.sender,
        message_id: res.message_id,
        message_type: res.message_type
    });

    this.$chat_space_container.append(
        this.make_message(res.content, time, chat_type, res.sender)
    );
    scroll_to_bottom(this.$chat_space_container);
  }

  render() {
    this.$wrapper.html(this.$chat_space);
    this.setup_events();

    scroll_to_bottom(this.$chat_space_container);
  }
}
