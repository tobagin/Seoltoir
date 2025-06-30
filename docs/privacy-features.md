Privacy Features in Seoltóir

Seoltóir is built with your privacy at its core. This section explains the various features designed to protect you from online tracking, ads, and data collection.
1. Ad and Tracker Blocking

Seoltóir employs a powerful content blocker to prevent unwanted ads and trackers from loading.

    How it Works: We utilize standard Adblock Plus (ABP) compatible filter lists. When a website attempts to load a resource (like an image, script, or iframe) or an element on the page matches a rule in these lists, Seoltóir blocks it.

    Filter Lists: By default, Seoltóir uses popular filter lists like EasyList and EasyPrivacy. These lists are regularly updated.

    Blocked Count: The small number in the header bar (XX blocked) indicates how many ads, trackers, and other unwanted resources have been blocked on the current page.

Configuration

You can manage ad and tracker blocking in Preferences > Privacy & Security > Content Blocking:

    Enable Ad and Tracker Blocking: Toggle this switch to turn the ad blocker on or off.

    Filter List URLs: Here you can see the URLs of the filter lists Seoltóir downloads. You can add or remove URLs (comma-separated), but be cautious when modifying these as invalid URLs may break blocking.

        Updating Filter Lists: Seoltóir automatically attempts to download and apply updated filter lists periodically and when settings change.

2. Fingerprinting Resistance

Websites can try to "fingerprint" your browser by collecting unique characteristics of your system (e.g., screen size, fonts, hardware details) to identify you across sites. Seoltóir implements several measures to resist this:
A. User Agent Spoofing

    What it is: Your browser sends a "User-Agent" string to websites, identifying your browser, operating system, and sometimes device. This can be used for tracking.

    Seoltóir's Protection: You can configure a generic User-Agent string to make your browser appear less unique.

    Configuration: Preferences > Privacy & Security > Fingerprinting Resistance > User Agent String. Leave empty for default WebKitGTK User Agent, or enter a custom one.

B. Canvas Fingerprinting Spoofing

    What it is: Websites can draw hidden images on a canvas and then analyze subtle differences in how your system renders them (due to GPU, drivers, fonts, etc.) to create a unique "canvas fingerprint."

    Seoltóir's Protection: Seoltóir adds imperceptible noise to canvas drawing operations (toDataURL, getImageData). This makes your canvas fingerprint unique on each attempt, preventing consistent tracking.

    Configuration: Preferences > Privacy & Security > Fingerprinting Resistance > Enable Canvas Fingerprinting Spoofing.

C. Font Enumeration Spoofing

    What it is: Websites can detect which fonts are installed on your system, which can be part of a unique fingerprint.

    Seoltóir's Protection: Seoltóir spoofs the list of fonts reported to websites, providing a generic, common set of fonts instead of your actual installed fonts.

    Configuration: Preferences > Privacy & Security > Fingerprinting Resistance > Enable Font Enumeration Spoofing.

D. Hardware Concurrency & Device Memory Spoofing

    What it is: Websites can query your CPU core count (navigator.hardwareConcurrency) and available RAM (navigator.deviceMemory), contributing to your unique fingerprint.

    Seoltóir's Protection: Seoltóir spoofs these values, reporting generic, randomized numbers within common ranges instead of exact system details.

    Configuration: Preferences > Privacy & Security > Fingerprinting Resistance > Enable Hardware Concurrency Spoofing.

E. WebRTC Control

    What it is: WebRTC (Web Real-Time Communication) is used for video calls, audio chats, etc. While useful, it can sometimes leak your local IP address, even if you're using a VPN.

    Seoltóir's Protection: You can completely disable WebRTC to prevent potential IP leaks.

    Configuration: Preferences > Privacy & Security > WebRTC > Enable WebRTC. Disabling might break video/audio calls on some sites.

F. Referrer Policy Control

    What it is: The "Referrer" header tells a website where you came from (the previous page's URL). This can be used by analytics and advertising networks.

    Seoltóir's Protection: You can choose how much referrer information is sent with requests.

    Configuration: Preferences > Privacy & Security > Referrer Policy. Options range from sending no referrer information (no-referrer) to sending full URLs (unsafe-url). strict-origin-when-cross-origin is a good balance for privacy.

3. Comprehensive Cookie & Site Data Management

Cookies and other forms of site storage (Local Storage, IndexedDB) are primary tools for tracking your online activity and remembering your preferences.

    Third-Party Cookie Blocking: By default, Seoltóir blocks all third-party cookies, preventing many forms of cross-site tracking.

    Delete Non-Bookmarked Cookies on Close: You can configure Seoltóir to automatically delete all cookies from sites that you haven't explicitly bookmarked when the browser closes. This helps maintain a cleaner browsing profile.

        Configuration: Preferences > Privacy & Security > Cookie Management > Delete non-bookmarked cookies on close.

    Per-Site Data Management:

        Access: Right-click anywhere on a webpage or go to Menu > Manage Site Settings.

        Functionality: This dialog allows you to view and delete:

            Cookies: Individual cookies for the current domain.

            Site Data: Other persistent storage like Local Storage and IndexedDB for the current domain.

    Clear All Browsing Data:

        Access: Menu > Clear Browsing Data.

        Functionality: A dedicated dialog allows you to selectively clear:

            Browsing History

            Cookies and Site Data

            Cached Web Content

            Download History

        You can choose to clear data for "All Time".

4. Encrypted DNS (DoH/DoT)

DNS (Domain Name System) queries translate human-readable domain names (like google.com) into IP addresses. Unencrypted DNS queries can be intercepted by your ISP or others to track your online activity or even redirect you to malicious sites.

    DNS over HTTPS (DoH): Encrypts your DNS queries over an HTTPS connection.

    DNS over TLS (DoT): Encrypts your DNS queries over a dedicated TLS connection (similar to HTTPS, but on a different port).

    Seoltóir's Protection: Seoltóir supports both DoH and DoT, allowing you to choose an encrypted DNS provider. They are mutually exclusive; enabling one will disable the other.

    Configuration: Preferences > Privacy & Security > DNS over HTTPS / DNS over TLS. You can specify the provider's URL (for DoH) or Host and Port (for DoT).

5. HTTPS Everywhere

    What it is: Many websites support HTTPS (encrypted connection) but don't automatically redirect you from their HTTP version. HTTPS Everywhere rules ensure your connection is always encrypted when possible.

    Seoltóir's Protection: Seoltóir attempts to upgrade all HTTP connections to HTTPS based on a ruleset, enhancing your security and privacy by preventing passive eavesdropping.

    Configuration: Preferences > Privacy & Security > HTTPS Everywhere > Enable HTTPS Everywhere Rules.

6. JavaScript Control

JavaScript is essential for most modern websites, but it can also be used for tracking, fingerprinting, and displaying unwanted content.

    Global Control: You can enable or disable JavaScript for all websites by default.

        Configuration: Preferences > Privacy & Security > JavaScript Control > Enable JavaScript Globally.

    Per-Site Exceptions: For sites that require JavaScript to function (e.g., web applications, video players), you can create exceptions to either allow or block JavaScript specifically for that domain, overriding the global setting.

        Access: Right-click anywhere on a webpage or go to Menu > Manage Site Settings. Select the "JavaScript" tab.

7. Content Isolation (Container Tabs)

Container Tabs provide a powerful way to isolate your browsing activities into separate, independent contexts.

    How it Works: Each container tab uses its own unique WebKit.WebContext, meaning cookies, local storage, indexedDB, and cache are completely separate from other containers, regular tabs, and private tabs.

    Use Cases:

        Keep your shopping activity separate from your social media.

        Log into multiple accounts on the same website simultaneously (each in a different container).

        Isolate untrusted websites to prevent them from tracking your activity elsewhere.

    Access: Menu > New Tab > Containers > New Container Tab. You will be prompted to name your new container.

    Management: Containers are persistent. When you close a container tab, its data remains isolated for future use. (Future development might include a UI to manage/delete custom containers.)