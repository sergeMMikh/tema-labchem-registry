# Reagent label photos

Send a clear photograph of a reagent bottle label to the Telegram or WhatsApp bot. The bot reads the name, CAS number, catalogue number and manufacturer using OpenAI vision. It then searches the TEMA inventory. A CAS match has priority, followed by an exact catalogue number and an unambiguous exact name. An inventory match returns the reagent, packages, quantities and locations; the Sigma-Aldrich website is not contacted.

If the reagent is absent from the inventory, the bot searches the Sigma-Aldrich product catalogue. It returns the page title and description when the site responds, plus the direct search link. If direct access fails, an OpenAI web search limited to official Sigma-Aldrich pages attempts to find a source-backed summary. If both methods fail, the bot reports that and still provides the search link. Unreadable labels require a clearer image; the bot does not invent missing CAS numbers or product details.

After a miss, the bot asks whether to save the reagent. **No** cancels without writing anything. **Yes** opens a paginated list of active storage locations; selecting a location creates the reagent and one package there. The new package is marked **Pending review**. Quantity, lot and expiry are left blank, so it does not count as available stock until a laboratory user verifies and updates it on the website. The bot stores the recognized label fields and an official Sigma source URL when available. The choice expires after one hour or a bot process restart. Repeated taps cannot create a second record from the same choice.

## Setup and limits

Set `OPEN_AI_KEY` in the local `.env`; optionally set `OPEN_AI_VISION_MODEL` (default `gpt-4.1-mini`) and `OPEN_AI_SEARCH_MODEL` (default `gpt-5.4-mini`). Restart the Telegram worker and the WhatsApp web process after changing the environment. Telegram accepts a photo message; WhatsApp accepts an image message through the configured webhook. Maximum downloaded image size is 10 MB. Images are resized to 1800 pixels, converted to JPEG and sent to OpenAI for recognition; do not send confidential labels unless this external processing is acceptable. OpenAI image and web search usage may incur charges. Empty `TELEGRAM_SAVE_USER_IDS` and `WHATSAPP_SAVE_USER_IDS` let all users with bot access save; set comma-separated Telegram user IDs or WhatsApp numbers to restrict this later. The WhatsApp test-number restrictions still apply.

Sigma-Aldrich pages can be unavailable or change structure; in that case the link is provided without claiming a verified catalogue result. Photo identification depends on the legibility of the label and must be checked against the bottle before laboratory use.

References: [OpenAI image input](https://platform.openai.com/docs/guides/images-vision) · [Sigma-Aldrich catalogue](https://www.sigmaaldrich.com/PT/en/search/acetone?focus=products&term=acetone&type=product).
