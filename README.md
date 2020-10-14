# Bluebird
A Twitter bot that gathers deleted tweets

What this Twitter bot does
--------------------------
- You can send my account tweets and I will do tricks!
- I store tweets from the accounts you specify, for a reasonable window of time.
- I keep checking for the stored tweets, and if I find one that was deleted, I keep it forever. 
- I will stop storing tweets from an account, if you tell me to
- I will follow or stop following accounts you specify.
- You can ask me to change how often I check for new commands from you, or new/deleted tweets from the accounts I'm watching.
- I will send a tweet you give me to another account
- I will send a direct message you give me to another account
- I will send a list of the deleted tweets I've found so far to the email account you specify.
- I will destroy all my captured data, if you tell me to

Example commands you can tweet at the bot account
-------------------------------------------------
**@[bot account] capture @[target account]**
<br>`@mytwitterbot capture @Google`
<br>*Begin storing tweets from @Google and checking for deleted ones*
	
**@[bot account] uncapture @[target account]**
<br>`@mytwitterbot uncapture @Google`
<br>*Stop storing tweets from @Google*

**@[bot account] refresh [number of seconds]**
<br>`@mytwitterbot refresh 45`
<br>*Sleep for 45 seconds after finishing the tasks, and then wake up and do it again!*

**@[bot account] follow @[target account]**
<br>`@mytwitterbot follow @Google`
<br>*Begin following the @Google account (this really does nothing but add the account to "Following")*
	
**@[bot account] unfollow @[target account]**
<br>`@mytwitterbot follow @Google`
<br>*Unfollow the @Google account (this really does nothing but remove the account from "Following")*

**@[bot account] tweet [message]**
<br>`@mytwitterbot tweet @Google this is a message`
<br>*Send a tweet which mentions the @Google account*
	
**@[bot account] DM @[target account] [message]**
<br>`@mytwitterbot DM @Google this is a message`
<br>*Send a direct message to the @Google account*
	
**@[bot account] deleted [email address]**
<br>`@mytwitterbot deleted myemail@gmail.com`
<br>*Send a list of the deleted tweets captured so far to myemail@gmail.com*

**@[bot account] az5**
<br>`@mytwitterbot az5`
<br>*Destroy all data!*
