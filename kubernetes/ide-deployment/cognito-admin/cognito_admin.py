import streamlit as st
import boto3

USER_POOL_ID = "us-east-1_KsQSqvc9B"
session = boto3.Session(profile_name="cognito_admin_iesb")
client = session.client("cognito-idp", region_name="us-east-1")

st.title("IESB IDE - Cognito Whitelist")

# --- List users ---
st.subheader("Current Users")
users = client.list_users(UserPoolId=USER_POOL_ID)["Users"]
for u in users:
    email = next((a["Value"] for a in u["Attributes"] if a["Name"] == "email"), u["Username"])
    col1, col2 = st.columns([4, 1])
    col1.write(f"{email} — {u['UserStatus']}")
    if col2.button("Remove", key=u["Username"]):
        client.admin_delete_user(UserPoolId=USER_POOL_ID, Username=u["Username"])
        st.rerun()

# --- Add user ---
st.subheader("Add User")
email = st.text_input("Email")
temp_pass = st.text_input("Temporary Password", type="password")
if st.button("Add") and email and temp_pass:
    client.admin_create_user(
        UserPoolId=USER_POOL_ID,
        Username=email,
        TemporaryPassword=temp_pass,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
    )
    st.success(f"Added {email}")
    st.rerun()
