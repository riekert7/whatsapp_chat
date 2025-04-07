// frappe.Chat
// Author - Nihal Mittal <nihal@erpnext.com>

import {
  ChatBubble,
  ChatList,
  ChatSpace,
  ChatWelcome,
  get_settings,
  scroll_to_bottom,
} from './components';
frappe.provide('frappe.Chat');
frappe.provide('frappe.Chat.settings');

/** Spawns a chat widget on any web page */
frappe.Chat = class {
  constructor() {
    this.setup_app();
    this.setup_sound_handling();
  }

  /** Create all the required elements for chat widget */
  create_app() {
    this.$app_element = $(document.createElement('div'));
    this.$app_element.addClass('chat-app');
    this.$chat_container = $(document.createElement('div'));
    this.$chat_container.addClass('chat-container');
    $('body').append(this.$app_element);
    this.is_open = false;

    this.$chat_element = $(document.createElement('div'))
      .addClass('chat-element')
      .hide();

    this.$chat_element.append(`
			<span class="chat-cross-button">
				${frappe.utils.icon('close', 'lg')}
			</span>
		`);
    this.$chat_element.append(this.$chat_container);
    this.$chat_element.appendTo(this.$app_element);

    this.chat_bubble = new ChatBubble(this);
    this.chat_bubble.render();

    const navbar_icon_html = `
        <li class='nav-item dropdown dropdown-notifications 
          dropdown-mobile chat-navbar-icon' title="Show Chats" >
          ${frappe.utils.icon('small-message', 'md')}
          <span class="badge" id="chat-notification-count"></span>
        </li>
    `;

    if (this.is_desk === true) {
      $('header.navbar > .container > .navbar-collapse > ul').prepend(
        navbar_icon_html
      );
    }
    this.setup_events();
  }

  /** Setup sound handling to prevent 404 errors */
  setup_sound_handling() {
    // Override the play_sound function to handle missing sound files
    const originalPlaySound = frappe.utils.play_sound;
    frappe.utils.play_sound = (sound_name) => {
      console.log('Attempting to play sound:', sound_name);
      try {
        originalPlaySound(sound_name);
      } catch (error) {
        console.warn('Sound file not found or could not be played:', sound_name);
        // Silently fail - don't show errors to users
      }
    };
  }

  /** Load dependencies and fetch the settings */
  async setup_app() {
    try {
      console.log('Starting chat app setup...');
      const token = localStorage.getItem('guest_token') || '';
      const res = await get_settings(token);
      console.log('Chat settings received:', res);
      
      this.is_admin = res.is_admin;
      this.is_desk = 'desk' in frappe;

      if (res.enable_chat === false || (!this.is_desk && this.is_admin)) {
        console.log('Chat disabled or user not authorized');
        return;
      }

      this.create_app();
      console.log('Initializing socketio with port:', res.socketio_port);
      await frappe.socketio.init(res.socketio_port);
      console.log('Socketio initialized');

      frappe.Chat.settings = {};
      frappe.Chat.settings.user = res.user_settings;
      frappe.Chat.settings.unread_count = 0;

      // Log socket connection status
      console.log('Socket connection status:', frappe.socketio.socket?.connected);
      
      // Add socket event listeners for debugging
      if (frappe.socketio.socket) {
        console.log('Socket object available:', frappe.socketio.socket);
        
        // Log when socket connects
        frappe.socketio.socket.on('connect', () => {
          console.log('Socket connected event fired');
        });
        
        // Log when socket disconnects
        frappe.socketio.socket.on('disconnect', () => {
          console.log('Socket disconnected event fired');
        });
        
        // Log any socket errors
        frappe.socketio.socket.on('error', (error) => {
          console.error('Socket error:', error);
        });
        
        // Log any socket reconnection attempts
        frappe.socketio.socket.on('reconnect_attempt', (attemptNumber) => {
          console.log('Socket reconnection attempt:', attemptNumber);
        });
        
        // Log when socket reconnects
        frappe.socketio.socket.on('reconnect', (attemptNumber) => {
          console.log('Socket reconnected after', attemptNumber, 'attempts');
        });
      } else {
        console.warn('Socket object not available after initialization');
      }

      if (res.is_admin) {
        console.log('Setting up admin chat interface');
        this.chat_list = new ChatList({
          $wrapper: this.$chat_container,
          user: res.user,
          user_email: res.user_email,
          is_admin: res.is_admin,
        });
        this.chat_list.render();
      } else if (res.is_verified) {
        console.log('Setting up verified user chat interface');
        this.chat_space = new ChatSpace({
          $wrapper: this.$chat_container,
          profile: {
            room_name: res.guest_title,
            room: res.room,
            is_admin: res.is_admin,
            user: res.user,
            user_email: res.user_email,
          },
        });
      } else {
        console.log('Setting up welcome screen for unverified user');
        this.chat_welcome = new ChatWelcome({
          $wrapper: this.$chat_container,
          profile: {
            name: res.guest_title,
            is_admin: res.is_admin,
            chat_status: res.chat_status,
          },
        });
        this.chat_welcome.render();
      }
    } catch (error) {
      console.error('Error in chat app setup:', error);
    }
  }

  /** Shows the chat widget */
  show_chat_widget() {
    console.log('Showing chat widget');
    this.is_open = true;
    this.$chat_element.fadeIn(250);
    
    // If we have a chat space and it's visible, scroll to bottom
    if (typeof this.chat_space !== 'undefined' && $('.chat-space').is(':visible')) {
      scroll_to_bottom(this.chat_space.$chat_space_container);
    }
  }

  /** Hides the chat widget */
  hide_chat_widget() {
    console.log('Hiding chat widget');
    this.is_open = false;
    this.$chat_element.fadeOut(300);
  }

  setup_events() {
    const me = this;
    // Only handle clicks on the chat navbar icon
    $('.chat-navbar-icon').on('click', function () {
      me.chat_bubble.change_bubble();
    });
  }
};

$(function () {
  new frappe.Chat();
});
