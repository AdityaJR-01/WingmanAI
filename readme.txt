The requirements.txt file contatins all the python libraries required to run this project.
Use the following command to install all of them:

pip install -r requirements.txt

Once the libraries are installed, run the login.py file to kind of create a new account and store your access tokens in the users.json file.
Then run the main.py file to start and get running the main app. (Note: it temporarily asks you for your email to login, since it is not connected to the database)

Place client_secret.json inside config/ folder.
This file is NOT included in the repo for security reasons.
Also create a data directory for users.json file.

Here, the main.py file is supposed to: 
    First run the token_manager.py file in order to get the users' credentials and get the APIs working.
        This uses the functions from the Google_auth.py and linkedin_auth.py files to validate the apps. 
        The weather and websearch agents don't require any APIs tokens/validation as they don't personalize to specific users.
    Second, it calls for the memory function from memory/chat_memory.py which accesses the memory stored for each user in the memory directory.
    Then lastly it calls the Director Agent (Again specific to each user based on the apps they have granted permission for).
    After this the main function maintains the loop that lets the user chat until their work is done.

Progress:
- Created the agents and tools for the director to access them. 
- Also, added the email parameter for the agents to be able to access the tokens.
- Whenever making agents, name them as "{application_name}Agent" to maintain uniformity and also first letter should be capitalized.

What's next?
- Refine the ChatMemory class/function.
- Add multi-task handling.
- Connect a database to handle: Signup/Login, ChatMemory storage, client secrets, user credentials.
- Create a UI and apply the backend, frontend and the database.
