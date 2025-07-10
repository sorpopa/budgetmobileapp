import flet as ft
from firebase_admin import firestore
from google.cloud import firestore as fire


class FriendsManager:
    def __init__(self, user_id):
        self.user_id = user_id
        self.db = firestore.client()

    def search_users_by_email(self, email):
        """Search for users by email address"""
        try:
            users_ref = self.db.collection('users')
            query = users_ref.where(filter=fire.FieldFilter('email', '==', email)).limit(1)
            docs = query.stream()

            for doc in docs:
                user_data = doc.to_dict()
                if doc.id != self.user_id:  # Don't return current user
                    return {
                        'userId': doc.id,
                        'email': user_data.get('email'),
                        'displayName': user_data.get('displayName', email.split('@')[0])
                    }
            return None
        except Exception as e:
            print(f"Error searching users: {e}")
            return None

    def send_friend_request(self, target_user_id):
        """Send a friend request to another user"""
        try:
            # Check if request already exists
            existing_request = (self.db.collection('friendRequests')
                                .where(filter=fire.FieldFilter('from', '==', self.user_id))
                                .where(filter=fire.FieldFilter('to', '==', target_user_id))
                                .where(filter=fire.FieldFilter('status', '==', 'pending'))
                                .stream())

            if any(existing_request):
                return {"error": "Friend request already sent"}

            # Check if they're already friends
            if self.are_friends(target_user_id):
                return {"error": "Already friends with this user"}

            # Create friend request
            request_data = {
                'from': self.user_id,
                'to': target_user_id,
                'status': 'pending',
                'createdAt': firestore.SERVER_TIMESTAMP
            }

            doc_ref = self.db.collection('friendRequests').add(request_data)
            return {"success": True, "requestId": doc_ref[1].id}

        except Exception as e:
            return {"error": str(e)}

    def get_pending_requests(self):
        """Get pending friend requests for current user"""
        try:
            # Requests TO current user
            incoming_requests = []
            requests_ref = (self.db.collection('friendRequests')
                            .where(filter=fire.FieldFilter('to', '==', self.user_id))
                            .where(filter=fire.FieldFilter('status', '==', 'pending')))

            for doc in requests_ref.stream():
                request_data = doc.to_dict()
                # Get sender info
                sender_doc = self.db.collection('users').document(request_data['from']).get()
                if sender_doc.exists:
                    sender_data = sender_doc.to_dict()
                    incoming_requests.append({
                        'requestId': doc.id,
                        'from': request_data['from'],
                        'fromEmail': sender_data.get('email'),
                        'fromDisplayName': sender_data.get('displayName', 'Unknown'),
                        'createdAt': request_data.get('createdAt')
                    })

            return incoming_requests
        except Exception as e:
            print(f"Error getting requests: {e}")
            return []

    def respond_to_friend_request(self, request_id, accept=True):
        """Accept or reject a friend request"""
        try:
            request_ref = self.db.collection('friendRequests').document(request_id)
            request_doc = request_ref.get()

            if not request_doc.exists:
                return {"error": "Request not found"}

            request_data = request_doc.to_dict()

            if request_data['to'] != self.user_id:
                return {"error": "Not authorized"}

            if accept:
                # Create friendship
                friendship_id = f"{min(self.user_id, request_data['from'])}_{max(self.user_id, request_data['from'])}"
                friendship_data = {
                    'users': [self.user_id, request_data['from']],
                    'status': 'accepted',
                    'createdAt': firestore.SERVER_TIMESTAMP
                }

                self.db.collection('friendships').document(friendship_id).set(friendship_data)

                # Update request status
                request_ref.update({
                    'status': 'accepted',
                    'respondedAt': firestore.SERVER_TIMESTAMP
                })

                return {"success": True, "message": "Friend request accepted"}
            else:
                # Reject request
                request_ref.update({
                    'status': 'rejected',
                    'respondedAt': firestore.SERVER_TIMESTAMP
                })

                return {"success": True, "message": "Friend request rejected"}

        except Exception as e:
            return {"error": str(e)}

    def get_friends_list(self):
        """Get list of current user's friends"""
        try:
            friends = []
            friendships_ref = (self.db.collection('friendships')
                               .where(filter=fire.FieldFilter('users', 'array_contains', self.user_id))
                               .where(filter=fire.FieldFilter('status', '==', 'accepted')))

            for doc in friendships_ref.stream():
                friendship_data = doc.to_dict()
                print(f"friendship_data is {friendship_data}")
                # Get the other user's ID
                other_user_id = friendship_data['users'][0] if friendship_data['users'][1] == self.user_id else \
                friendship_data['users'][1]

                # Get other user's info
                user_doc = self.db.collection('users').document(other_user_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    print(f"user data: {user_data}")
                    friends.append({
                        'userId': other_user_id,
                        'email': user_data.get('email'),
                        'displayName': user_data.get('displayName'),
                        'friendshipId': doc.id
                    })
            print(f"data for friends retrieved from db: {friends}")
            return friends
        except Exception as e:
            print(f"Error getting friends: {e}")
            return []

    def are_friends(self, other_user_id):
        """Check if two users are friends"""
        try:
            friendship_id = f"{min(self.user_id, other_user_id)}_{max(self.user_id, other_user_id)}"
            friendship_doc = self.db.collection('friendships').document(friendship_id).get()

            if friendship_doc.exists:
                friendship_data = friendship_doc.to_dict()
                return friendship_data.get('status') == 'accepted'

            return False
        except Exception as e:
            print(f"Error checking friendship: {e}")
            return False

    def remove_friend(self, friend_user_id):
        """Remove a friend (delete friendship)"""
        try:
            friendship_id = f"{min(self.user_id, friend_user_id)}_{max(self.user_id, friend_user_id)}"
            self.db.collection('friendships').document(friendship_id).delete()
            return {"success": True, "message": "Friend removed"}
        except Exception as e:
            return {"error": str(e)}


class FriendsUI:
    def __init__(self, page: ft.Page, user_id):
        self.page = page
        self.user_id = user_id
        self.friends_manager = FriendsManager(user_id)

        # UI Controls
        self.search_email_field = ft.TextField(label="Search by email", )
        self.search_result_text = ft.Text()
        self.search_results_container = ft.Column([
            self.search_result_text
        ])
        self.status_text = ft.Text()
        self.friends_list = ft.Column()
        self.requests_list = ft.Column()

        self.refresh_data()

    def create_friends_view(self):
        """Create the friends management UI"""

        return ft.Container(
            content=ft.Column([
                ft.Text("Friends Management", size=24, weight=ft.FontWeight.BOLD),

                # Search for new friends
                ft.Row([
                    ft.FloatingActionButton(text="Add Friend",
                                            icon=ft.icons.ADD,
                                            bgcolor=ft.colors.LIME_300,
                                            data=0,
                                            on_click=self.show_add_friend_dialog,
                                            ),
                ], alignment=ft.MainAxisAlignment.END),

                # Current friends
                ft.Container(
                    content=ft.Column([
                        ft.Text("Your Friends", size=18, weight=ft.FontWeight.BOLD),
                        self.friends_list
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.colors.GREY_400),
                    border_radius=10
                ),

                # Pending friend requests
                ft.Container(
                    content=ft.Column([
                        ft.Text("Friend Requests", size=18, weight=ft.FontWeight.BOLD),
                        self.requests_list
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.colors.GREY_400),
                    border_radius=10,
                    margin=ft.margin.only(bottom=20)
                ),

                ft.ElevatedButton("Refresh",
                                  bgcolor=ft.colors.LIME_300,
                                  on_click=self.refresh_clicked)
            ]),
            padding=20
        )



    def search_user(self, e):
        """Search for a user by email"""
        email = self.search_email_field.value.strip()
        if not email:
            self.update_search_results("Please enter an email address")
            return

        user = self.friends_manager.search_users_by_email(email)

        if user:
            # Check if already friends
            if self.friends_manager.are_friends(user['userId']):
                self.update_search_results(f"Already friends with {user['email']}")
            else:
                # Show user found with send request button
                self.show_user_found(user)
        else:
            self.update_search_results("No user found with that email")

    def update_search_results(self, message, show_button=False, user_data=None):
        """Update the search results container"""
        # Clear existing content
        self.search_results_container.controls.clear()

        # Add the message
        self.search_results_container.controls.append(
            ft.Text(message)
        )

        # Add button if needed
        if show_button and user_data:
            send_button = ft.ElevatedButton(
                "Send Friend Request",
                on_click=lambda e: self.send_friend_request(user_data['userId'], user_data),
                style=ft.ButtonStyle(
                    bgcolor=ft.colors.BLUE,
                    color=ft.colors.WHITE
                )
            )
            self.search_results_container.controls.append(send_button)

        self.page.update()

    def show_user_found(self, user):
        """Show user found with send request button"""
        message = f"Found: {user['displayName']} ({user['email']})"
        self.update_search_results(message, show_button=True, user_data=user)

    def send_friend_request(self, target_user_id, user_data):
        """Send friend request and update UI"""
        result = self.friends_manager.send_friend_request(target_user_id)

        if result.get('success'):
            # Clear the search results and show success message
            self.update_search_results(f"Friend request sent to {user_data['displayName']}!")
            self.search_email_field.value = ""  # Clear the search field

            # Show success in status text
            self.status_text.value = "Friend request sent successfully!"
            self.status_text.color = ft.colors.GREEN
        else:
            # Show error message
            error_msg = result.get('error', 'Failed to send friend request')
            self.status_text.value = f"Error: {error_msg}"
            self.status_text.color = ft.colors.RED

        self.page.update()

    def clear_search_results(self):
        """Clear search results and reset UI"""
        self.search_results_container.controls.clear()
        self.search_results_container.controls.append(self.search_result_text)
        self.search_result_text.value = ""
        self.status_text.value = ""
        self.page.update()

    def accept_request(self, request_id):
        """Accept a friend request"""
        result = self.friends_manager.respond_to_friend_request(request_id, accept=True)
        self.handle_request_response(result)

    def reject_request(self, request_id):
        """Reject a friend request"""
        result = self.friends_manager.respond_to_friend_request(request_id, accept=False)
        self.handle_request_response(result)

    def handle_request_response(self, result):
        """Handle the response from accepting/rejecting a request"""
        if "error" in result:
            self.status_text.value = f"Error: {result['error']}"
            self.status_text.color = ft.colors.RED
        else:
            self.status_text.value = result['message']
            self.status_text.color = ft.colors.GREEN
            self.refresh_data()

        self.page.update()

    def remove_friend(self, friend_user_id, friend_name):
        """Remove a friend"""
        # In a real app, you might want to show a confirmation dialog
        result = self.friends_manager.remove_friend(friend_user_id)

        if "error" in result:
            self.status_text.value = f"Error: {result['error']}"
            self.status_text.color = ft.colors.RED
        else:
            self.status_text.value = f"Removed {friend_name} from friends"
            self.status_text.color = ft.colors.GREEN
            self.refresh_data()

        self.page.update()

    def refresh_data(self):
        """Refresh friends and requests data"""
        # Clear existing data
        self.friends_list.controls.clear()
        self.requests_list.controls.clear()

        # Load friends
        friends = self.friends_manager.get_friends_list()
        if friends:
            for friend in friends:
                friend_row = ft.Row([
                    ft.Text(f"{friend['displayName']}" , color=ft.colors.GREEN_600, size=20, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton(
                        "Remove",
                        color=ft.colors.RED,
                        on_click=lambda e, fid=friend['userId'], fname=friend['displayName']: self.remove_friend(fid,
                                                                                                                 fname)
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                self.friends_list.controls.append(friend_row)
        else:
            self.friends_list.controls.append(ft.Text("No friends yet"))

        # Load friend requests
        requests = self.friends_manager.get_pending_requests()
        if requests:
            for request in requests:
                request_row = ft.Row([
                    ft.Text(f"From: {request['fromDisplayName']} ({request['fromEmail']})"),
                    ft.Row([
                        ft.ElevatedButton(
                            "Accept",
                            color=ft.colors.GREEN,
                            on_click=lambda e, rid=request['requestId']: self.accept_request(rid)
                        ),
                        ft.ElevatedButton(
                            "Reject",
                            color=ft.colors.RED,
                            on_click=lambda e, rid=request['requestId']: self.reject_request(rid)
                        )
                    ])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                self.requests_list.controls.append(request_row)
        else:
            self.requests_list.controls.append(ft.Text("No pending requests"))

    def refresh_clicked(self, e):
        """Refresh button clicked"""
        self.refresh_data()
        self.status_text.value = "Refreshed!"
        self.status_text.color = ft.colors.GREEN
        self.page.update()

    def show_add_friend_dialog(self, e):

        self.add_friend_form_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add New Friend"),
            content=ft.Column([
                ft.Text("Add New Friend", size=10, weight=ft.FontWeight.BOLD),
                ft.Column([
                    self.search_email_field,
                    ft.ElevatedButton("Search", on_click=self.search_user)
                ]),
                self.search_results_container,
                self.status_text,
            ]),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.close_add_friend_dialog()),
            ],
        )

        self.page.dialog = self.add_friend_form_dialog
        self.add_friend_form_dialog.open = True
        self.page.update()

    def close_add_friend_dialog(self):
        self.add_friend_form_dialog.open = False
        self.page.update()