import ChatRoom from './chat_room';
import ChatAddRoom from './chat_add_room';
import ChatUserSettings from './chat_user_settings';
import { get_rooms, mark_message_read } from './chat_utils';

export default class ChatList {
  constructor(opts) {
    this.$wrapper = opts.$wrapper;
    this.user = opts.user;
    this.user_email = opts.user_email;
    this.is_admin = opts.is_admin;
    this.setup();
  }

  setup() {
    this.$chat_list = $(document.createElement('div'));
    this.$chat_list.addClass('chat-list');
    this.setup_header();
    this.setup_search();
    this.fetch_and_setup_rooms();
    this.setup_socketio();
  }

  setup_header() {
    const chat_list_header_html = `
			<div class='chat-list-header'>
				<h3>${__('Chats')}</h3>
        <div class='chat-list-icons'>
          <div class='add-room' 
            title='Create Private Room'>
            ${frappe.utils.icon('users', 'md')}
          </div>
          <div class='user-settings' 
          title='Settings' style="display:none">
          ${frappe.utils.icon('setting-gear', 'md')}
          </div>
        </div>
			</div>
		`;
    this.$chat_list.append(chat_list_header_html);
  }

  setup_search() {
    const chat_list_search_html = `
		<div class='chat-search'>
			<div class='input-group'>
				<input class='form-control chat-search-box'
				type='search' 
				placeholder='${__('Search conversation')}'
				>	
				<span class='search-icon'>
					${frappe.utils.icon('search', 'sm')}
				</span>
			</div>
		</div>
		`;
    this.$chat_list.append(chat_list_search_html);
  }

  async fetch_and_setup_rooms() {
    try {
      const res = await get_rooms(this.user_email);
      this.rooms = res;
      this.setup_rooms();
      this.render_messages();
    } catch (error) {
      frappe.msgprint({
        title: __('Error'),
        message: __('Something went wrong. Please refresh and try again.'),
      });
    }
  }

  setup_rooms() {
    this.$chat_rooms_container = $(document.createElement('div'));
    this.$chat_rooms_container.addClass('chat-rooms-container');
    this.chat_rooms = [];
    console.log(this.rooms)
    this.rooms.forEach((element) => {
      let profile = {
        user: this.user,
        user_email: element.mobile_no,
        last_message: element.last_message,
        last_date: element.modified,
        is_admin: this.is_admin,
        room: element.name,
        is_read: element.is_read,
        room_name: element.contact_name,
        room_type: element.type,
        opposite_person_email: element.mobile_no,
      };

      this.chat_rooms.push([
        profile.room,
        new ChatRoom({
          $wrapper: this.$wrapper,
          $chat_rooms_container: this.$chat_rooms_container,
          chat_list: this,
          element: profile,
        }),
      ]);
    });
    this.$chat_list.append(this.$chat_rooms_container);
  }

  fitler_rooms(query) {
    for (const room of this.chat_rooms) {
      const txt = room[1].profile.room_name.toLowerCase();
      if (txt.includes(query)) {
        room[1].$chat_room.show();
      } else {
        room[1].$chat_room.hide();
      }
    }
  }

  create_new_room(profile) {
    this.chat_rooms.unshift([
      profile.room,
      new ChatRoom({
        $wrapper: this.$wrapper,
        $chat_rooms_container: this.$chat_rooms_container,
        chat_list: this,
        element: profile,
      }),
    ]);
    this.chat_rooms[0][1].render('prepend');
  }

  setup_events() {
    const me = this;
    
    // Handle chat room click
    this.$wrapper.on('click', '.chat-room', function() {
        const room = $(this).data('room');
        console.log('Chat room clicked:', room);
        
        // Get the chat room data
        const chatRoom = me.chat_rooms.find(room => room.room === room);
        if (chatRoom) {
            console.log('Opening chat room:', chatRoom);
            
            // Create and show chat space
            frappe.Chat.show_chat_space(chatRoom);
            
            // Mark as read only when user clicks on the chat room
            if (chatRoom.is_read === 0) {
                console.log('Marking message as read from chat_list.js click handler');
                mark_message_read(room);
            } else {
                console.log('Message already marked as read, skipping mark_message_read call');
            }
        }
    });
    
    // Handle refresh button click
    this.$wrapper.on('click', '.refresh-chats', function() {
        me.refresh();
    });
    
    // Handle search input
    this.$wrapper.find('.search-chats').on('input', function() {
        const searchTerm = $(this).val().toLowerCase();
        me.filter_chat_rooms(searchTerm);
    });

    $('.add-room').on('click', function (e) {
      if (typeof me.chat_add_room_modal === 'undefined') {
        me.chat_add_room_modal = new ChatAddRoom({
          user: me.user,
          user_email: me.user_email,
        });
      }
      me.chat_add_room_modal.show();
    });

    $('.user-settings').on('click', function (e) {
      if (typeof me.chat_user_settings === 'undefined') {
        me.chat_user_settings = new ChatUserSettings();
      }
      me.chat_user_settings.show();
    });
  }

  render_messages() {
    this.$chat_rooms_container.empty();
    for (const element of this.chat_rooms) {
      element[1].render('append');
    }
  }

  render() {
    this.$wrapper.html(this.$chat_list);
    this.setup_events();
  }

  move_room_to_top(chat_room_item) {
    this.chat_rooms = [
      chat_room_item,
      ...this.chat_rooms.filter((item) => item !== chat_room_item),
    ];
  }

  setup_socketio() {
    const me = this;
    console.log('Setting up chat list sockets');
    
    // Log all available socket events before registering new ones
    if (frappe.socketio.socket) {
        console.log('Socket object available in chat list setup');
        
        // Check if the socket is connected
        console.log('Socket connected status in chat list:', frappe.socketio.socket.connected);
        
        // Log existing listeners if possible
        if (frappe.socketio.socket.listeners) {
            console.log('Existing socket listeners:', frappe.socketio.socket.listeners);
        }
    } else {
        console.warn('Socket object not available in chat list setup');
    }
    
    frappe.realtime.on('latest_chat_updates', function (res) {
        console.log('Received latest chat update in chat_list.js:', res);
        //Find the room with the specified room id
        const chat_room_item = me.chat_rooms.find(
            (element) => element[0] === res.room
        );

        if (typeof chat_room_item === 'undefined') {
            console.log('No matching chat room found for update');
            return;
        }

        if (
            !$('.chat-element').is(':visible') &&
            frappe.Chat.settings.user.enable_notifications === 1
        ) {
            console.log('Playing notification sound');
            frappe.utils.play_sound('chat-notification');
        }

        const message =
            res.content.length > 24
                ? res.content.substring(0, 24) + '...'
                : res.content;

        chat_room_item[1].set_last_message(message, res.creation);

        // Check conditions for marking as read
        const chatListVisible = $('.chat-list').length > 0;
        const chatSpaceVisible = $('.chat-space').length > 0;
        const chatListIsVisible = $('.chat-list').is(':visible');
        
        console.log('Mark as read conditions in chat_list.js:', {
            chatListVisible,
            chatSpaceVisible,
            chatListIsVisible,
            shouldMarkAsRead: chatSpaceVisible && !chatListIsVisible
        });

        if (chatListVisible) {
            chat_room_item[1].set_as_unread();
            chat_room_item[1].move_to_top();
            me.move_room_to_top(chat_room_item);
        } else if (chatSpaceVisible && !chatListIsVisible) {
            // Only mark as read if we're in the chat space and not in the chat list
            console.log('Marking message as read from chat_list.js');
            mark_message_read(res.room);
        } else {
            console.log('Not marking as read from chat_list.js - conditions not met');
        }
    });
    
    console.log('Registered latest_chat_updates event listener');

    frappe.realtime.on('new_room_creation', function (res) {
        console.log('Received new room creation:', res);
        if (
            !$('.chat-element').is(':visible') &&
            frappe.Chat.settings.user.enable_notifications === 1
        ) {
            console.log('Playing notification sound for new room');
            frappe.utils.play_sound('chat-notification');
        }

        res.user = me.user;
        res.is_admin = me.is_admin;
        res.user_email = me.user_email;
        me.create_new_room(res);
    });
    
    console.log('Registered new_room_creation event listener');

    frappe.realtime.on('private_room_creation', function (res) {
        console.log('Received private room creation:', res);
        if (
            !$('.chat-element').is(':visible') &&
            frappe.Chat.settings.user.enable_notifications === 1
        ) {
            console.log('Playing notification sound for private room');
            frappe.utils.play_sound('chat-notification');
        }

        if (res.members.includes(me.user_email)) {
            if (res.room_type === 'Direct') {
                res.room_name =
                    res.member_names[0]['email'] == me.user_email
                        ? res.member_names[1]['name']
                        : res.member_names[0]['name'];

                res.opposite_person_email =
                    res.member_names[0]['email'] == me.user_email
                        ? res.member_names[1]['email']
                        : res.member_names[0]['email'];
            }

            res.user = me.user;
            res.is_admin = me.is_admin;
            res.user_email = me.user_email;
            me.create_new_room(res);
        }
    });
    
    console.log('Registered private_room_creation event listener');
  }
}
