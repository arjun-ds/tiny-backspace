@web_app.post("/code")
async def create_code_changes(request: CodeRequest):
    """Main endpoint that streams the coding process"""
    # TODO: Look into ways to further improve the streaming experience
    