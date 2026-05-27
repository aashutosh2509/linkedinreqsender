import asyncio
import os
from playwright.async_api import async_playwright

async def run():
    base_dir = r'c:\Users\lenovo\linkedin req sender\linkedin_user_data'
    profiles = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    
    found = False
    async with async_playwright() as p:
        for profile in profiles:
            profile_path = os.path.join(base_dir, profile)
            try:
                ctx = await p.chromium.launch_persistent_context(profile_path, headless=True)
                state = await ctx.storage_state()
                for cookie in state['cookies']:
                    if cookie['name'] == 'li_at':
                        print('\n======================================================')
                        print(f'✅ FOUND SECURE COOKIE IN PROFILE: {profile}')
                        print('======================================================\n')
                        print(cookie['value'])
                        print('\n======================================================')
                        found = True
                        break
                await ctx.close()
            except Exception as e:
                pass
            if found: break
            
    if not found:
        print('ERROR: li_at cookie not found in ANY profile! Make sure you actually logged into LinkedIn.')

asyncio.run(run())
