# Signally Home/Away Security Mode

Admins and family members, but not guests, will have the option to toggle the system between **Home** and **Away** from the app.

This mode tells Signally how aggressive the security behavior should be:

- **Home mode:** Someone trusted is home. The system should relax security behavior and avoid loud intruder alerts from presence alone.
- **Away mode:** The home is armed. The system should be alert and notify on new devices, unknown presence, or suspicious entries into the home.

The mode should be synchronized across the whole household/security circle. For example, if the dad presses **Away**, every family member/admin phone connected to that Signally home should update its UI and show that the system is now in Away mode.

This should function like a regular home security system arm/disarm flow:

- Family/admin users can arm or disarm the home.
- Guests cannot change the security mode.
- All authorized household users see the same current mode.
- Detection logic should use this mode when deciding whether to log activity quietly, send a soft notification, or raise an intruder alert.

Core rule:
 
```text
CSI/probing/ARP detect signals.
Home/Away mode decides how suspicious those signals are.
```

This avoids relying only on ARP TTL or phone activity to decide if somebody is home. A family member may be home even if their phone has been asleep for a long time, so the system should not assume "nobody is home" just because an approved phone has not answered ARP recently.
