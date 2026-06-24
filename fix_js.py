import re

with open('automation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the JS evaluation block logic in both places.
# We'll use regex to find the body of the evaluate function for the connection status checker.
# The body always starts with `const topCard = ...` or `const nameHeader = ...` and ends with `return { status: "Not Started" };`

new_logic = """// Scope STRICTLY to the top card
                          const nameHeader = document.querySelector('main h1');
                          const topCard = nameHeader ? (nameHeader.closest('.artdeco-card') || nameHeader.closest('section') || nameHeader.parentElement?.parentElement?.parentElement || document) : (document.querySelector('main section') || document.querySelector('main [class*="top-card"]') || document);
                          
                          const actions = Array.from(topCard.querySelectorAll('button, a'));
                          const allSpans = Array.from(topCard.querySelectorAll('span, div, button, a'));
                          
                          // 1. First Priority: Check for explicit connection degree badges
                          let degree = null;
                          for (const el of allSpans) {
                              if (!el.offsetHeight && !el.offsetWidth) continue;
                              const text = el.textContent.trim();
                              if (/^[A-Za-z\\s?]*(1st|2nd|3rd|4th\\+)[A-Za-z\\s?]*$/i.test(text) || /^\\b(1st)\\b/i.test(text)) {
                                  degree = text.includes('1st') ? "1st" : "other";
                                  break;
                              }
                          }
                          
                          if (degree === "1st") {
                              return { status: "Connected" };
                          }
                          
                          // 2. Second Priority: Check for Messaging thread links (Connected users)
                          for (const el of actions) {
                              if (!el.offsetHeight && !el.offsetWidth) continue;
                              const href = el.getAttribute('href') || '';
                              const text = el.textContent.trim().toLowerCase();
                              if (href.includes('/messaging/thread/') || text === 'message') {
                                  if (!text.includes('inmail')) {
                                      return { status: "Connected" };
                                  }
                              }
                          }
                          
                          // 3. Third Priority: Check for Pending / Sent buttons
                          const hasPending = actions.some(el => {
                              if (!el.offsetHeight && !el.offsetWidth) return false;
                              const text = el.textContent.trim().toLowerCase();
                              const label = (el.getAttribute('aria-label') || '').toLowerCase();
                              if (text === 'pending' || text === 'sent' || label.includes('pending') || label.includes('sent connection')) return true;
                              if (text.includes('pending') || text.includes('invitation sent') || text.includes('request sent')) return true;
                              return false;
                          });
                          
                          if (hasPending) {
                              return { status: "Pending" };
                          }
                          
                          // 4. Fallback: If nothing above matched, check for a "Connect" button
                          const hasConnect = actions.some(el => {
                              if (!el.offsetHeight && !el.offsetWidth) return false;
                              const text = el.textContent.trim().toLowerCase();
                              const label = (el.getAttribute('aria-label') || '').toLowerCase();
                              return (text === 'connect' || (label.includes('invite') && label.includes('connect'))) && !text.includes('remove') && !label.includes('remove');
                          });
                          
                          if (hasConnect || degree === "other") {
                              return { status: "Not Started" };
                          }
                          
                          return { status: "Not Started" };"""

# We'll replace the content inside evaluate(...)
# Find the first evaluate block
pattern1 = re.compile(r'page\.evaluate\(r?"""\s*\(\)\s*=>\s*\{.*?(return\s*\{\s*status:\s*"Not Started"\s*\};\s*\}\s*)"""\)', re.DOTALL)
pattern2 = re.compile(r'page\.evaluate\("""\s*\(\)\s*=>\s*\{.*?(return\s*\{\s*status:\s*"Not Started"\s*\};\s*\}\s*)"""\)', re.DOTALL)

def repl(m):
    return 'page.evaluate("""\n                      () => {\n' + new_logic + '\n                      }\n                  """)'

content = pattern1.sub(repl, content)
content = pattern2.sub(repl, content)

with open('automation.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced successfully.")
