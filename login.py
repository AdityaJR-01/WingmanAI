from auth.google_auth import login_user as login_google
from auth.linkedin_auth import login_linkedin_user
from auth.token_manager import save_credentials

def main():
    email = input("Enter your email: ").strip()
    
    print("\n--- Google Service Selection ---")
    print("Select Google apps to connect: [gmail, calendar, docs, drive]")
    selected_google = input("Enter comma-separated Google apps: ").split(",")
    selected_google = [a.strip() for a in selected_google if a.strip()]
    
    if selected_google:
        login_google(email, selected_google)

    print("\n--- Other Service Selection ---")
    selected_other = input("Connect LinkedIn? (yes/no): ").strip().lower()
    
    if selected_other == "yes":
        try:
            # We assume login_linkedin_user() returns the required LinkedIn token dict
            linkedin_tokens = login_linkedin_user() 
            
            # --- FINAL INTEGRATION ---
            save_credentials(email, "linkedin", linkedin_tokens)
            print(f"✅ LinkedIn tokens retrieved and saved for {email}.")
        except Exception as e:
            print(f"❌ Failed to connect LinkedIn: {e}")
    # NOTE: The rest of the saving logic needs to be integrated with the Token Manager!

if __name__ == "__main__":
    main()