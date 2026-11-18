# Reagent label photos

Send a clear photograph of a reagent bottle label to the Telegram or WhatsApp bot. The bot reads the name, CAS number, catalogue number and manufacturer using OpenAI vision. It then searches the TEMA inventory. A CAS match has priority, followed by an exact catalogue number and an unambiguous exact name. An inventory match returns the reagent, packages, quantities and locations; the Sigma-Aldrich website is not contacted.

If the reagent is absent from the inventory, the bot searches the Sigma-Aldrich product catalogue. It returns the verified page title and description when the site responds, plus the direct search link. If the site is unavailable, the bot reports that and still provides the link. Unreadable labels require a clearer image; the bot does not invent missing CAS numbers or product details. The lookup never changes inventory.

## Setup and limits

Set `OPEN_AI_KEY` in the local `.env`; optionally set `OPEN_AI_VISION_MODEL` (default `gpt-4.1-mini`). Restart the Telegram worker and the WhatsApp web process after changing the environment. Telegram accepts a photo message; WhatsApp accepts an image message through the configured webhook. Maximum downloaded image size is 10 MB. Images are resized to 1800 pixels, converted to JPEG and sent to OpenAI for recognition; do not send confidential labels unless this external processing is acceptable. OpenAI API usage may incur charges. Existing bot allowlists also apply to photos. The WhatsApp test-number restrictions still apply.

Sigma-Aldrich pages can be unavailable or change structure; in that case the link is provided without claiming a verified catalogue result. Photo identification depends on the legibility of the label and must be checked against the bottle before laboratory use.

References: [OpenAI image input](https://platform.openai.com/docs/guides/images-vision) · [Sigma-Aldrich catalogue](https://www.sigmaaldrich.com/PT/en/search/acetone?focus=products&term=acetone&type=product).
