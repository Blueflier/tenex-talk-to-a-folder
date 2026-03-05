"""Google userinfo verification returning sub claim."""
import aiohttp
from fastapi import HTTPException


async def get_google_user_id(access_token: str) -> str:
    """Verify Google access token and return the user's sub claim.

    Calls the Google userinfo endpoint with the provided access token.
    Returns the 'sub' claim (stable user identifier) on success.
    Raises HTTPException(401) if the token is invalid.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        ) as r:
            if r.status != 200:
                raise HTTPException(
                    status_code=401, detail="Invalid access token"
                )
            info = await r.json()
            return info["sub"]
