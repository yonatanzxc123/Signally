# Signally
**Workshop - Networking applications**
**Made by - Yehonatan Segev & Idan Yosifov**

## Table of Contents
1. [Introduction](#introduction)
2. [Specification](#specification)
3. [Non-functional requirements](#non-functional-requirements)
4. [External dependencies](#external-dependencies)
5. [Design](#design)
6. [Appendices](#appendices)

---

## Introduction

### Background and Motivation
Modern security and occupancy monitoring solutions often rely on sensors like cameras, motion detectors, or wearables. However, these approaches can be intrusive (violating privacy), expensive, or impractical in certain environments.

To address these limitations, we propose leveraging **Wi-Fi sensing** technology as a non-intrusive alternative. Wi-Fi sensing uses the existing wireless signals in an environment to detect disturbances caused by people or devices. Specifically, by analyzing **Channel State Information (CSI)** from Wi-Fi signals, it is possible to recognize patterns or distortions caused by human/smartphones' presence or movement.

This approach preserves privacy (no cameras or wearable trackers needed) and can work through obstacles, making it suitable for indoor security monitoring.

Our project, **Signally**, builds on this concept to provide a novel intrusion detection and occupancy monitoring system. It aims to detect the presence of a person or a smartphone device in each area using only Wi-Fi signals, without any cameras or dedicated sensors.

### Project Goal
The goal of **Signally** is to develop a system that can collect Wi-Fi CSI data, preprocess and analyze it, and then infer meaningful occupancy information in real time.

In particular, the system should be able to:
* **Detect and identify human presence (or a personal device)** in the monitored space (e.g., determine if someone is present or not).
* **Distinguish between an authorized user and a potential intruder** ("friend or foe" detection), for example by recognizing known devices or patterns associated with household members.
* **Trigger real-time alerts** when unauthorized presence is detected.
* **Operate with minimal user involvement**, providing an easy-to-use interface for monitoring and requiring little manual calibration or input from the user.

By achieving these objectives, **Signally** will offer a simple yet effective security tool that leverages Wi-Fi networks signals to sense occupancy. The next sections detail the expected functionality (Specification) and the internal design & architecture (Design) of the proposed solution.

---

## Specification

### Target users
The primary target users for this system are individuals and small organizations who need a lightweight indoor security or occupancy monitoring solution. Examples include: homeowners, apartment renters, small office owners, or any user interested in detecting intruders or monitoring presence in a private space **without deploying cameras or wearable devices**.

The system is designed for **small-scale environments** (such as a single apartment, house, or small office floor), where a single Wi-Fi-based sensor device can cover the area of interest.

### System features
The following are the main features of the proposed system.

**Core Features (MVP):**
* **Wi-Fi Signal Data Collection:** Continuously collect Wi-Fi Channel State Information (CSI) measurements (known as fingerprints) using a monitoring device in the environment.
* **Data Streaming and Storage:** Transmit the collected CSI data to a backend service in real-time for processing and log the data in a storage system for further analysis or auditing.
* **Real-Time Presence Inference:** Analyze the incoming data stream to determine if a person or a device is present. The system will interpret patterns in the CSI to decide whether the current state is "occupied by someone" or "empty," and if occupied, whether the entity is recognized (authorized) or unknown.
* **Dashboard for Monitoring:** Provide a user-facing dashboard which displays the current state of the monitored area. This includes showing whether someone is detected, the system's confidence level in the detection, and live charts or signal metrics. The dashboard updates in near real-time and shows a log of recent events.

**Optional Features:**
* **Activity Classification:** Determine the nature of the detected subject's activity or motion (for example, distinguishing between someone moving vs. standing still, or even specific postures). This can extend the system to basic activity recognition.
* **Multi-Zone Support:** Support multiple sensing devices to cover different zones or rooms, allowing the system to monitor a larger area or multiple separate areas simultaneously.
* **Identity Recognition:** Recognize specific individuals by their unique signal "signature" (for instance, we might use gait analysis or device-specific patterns in the Wi-Fi signal). This would enable the system to not only detect a presence but possibly identify who it is (among known users).

### User Flows/Scenarios
To illustrate how the system will be used, here are a few key usage scenarios and workflows for Signally:

**Scenario 1 - Real-Time monitoring:**
1. Admin opens the Signally monitoring interface to check status.
2. The system immediately displays live information about the monitored area's occupancy status, along with a confidence score or indicator.
3. As time progresses, the dashboard continues to update in real-time the status and logs.

**Scenario 2 - Intrusion Alerts:**
1. The system is running in the background while the admin is not actively watching the dashboard.
2. Suppose an unauthorized person (intruder) enters the monitored space while no known user is present.
3. Signally detects the person's presence via Wi-Fi signal disturbances. It checks against known signatures or devices (to see if this might be a household member or authorized device).
4. Failing to find a match, it classifies the event as an **unknown intruder**.
5. The system automatically triggers an alert. (For example, it can send a push notification to the administrator's smartphone and/or an email).
6. The alert includes information such as the time of detection and the fact that an unknown presence was detected.

**Scenario 3 - Calibration and Setup:**
1. The admin initiates a one-time setup process to calibrate and define the physical boundaries of the monitored area.
2. The system guides the admin (e.g., through the web interface) to walk to specific corners or points in the house.
3. These CSI patterns are recorded and stored as a baseline map for known empty regions.
4. The admin can label zones (e.g., Living Room, Entry Hall), and mark known entrances and exits (e.g., front door).
5. This allows the system to contextualize future presence detection with spatial awareness.

**Scenario 4 (optional) - Recording and Baseline Learning:**
1. Admin initiates a CSI recording session, useful for training or debugging.
2. CSI data is continuously collected for a defined window of time.
3. The system analyzes this data to learn the "normal" environmental signature (baseline) when no human is present.
4. Future sessions can be compared to this profile to improve detection accuracy and reduce false positives. (This module could include download/replay features).

---

## Non-functional requirements
In addition to the functional features above, the system must meet several non-functional requirements to ensure it is practical and reliable:
* **Real-Time Performance:** The system should operate with low latency, i.e., it must process the incoming Wi-Fi data and update the dashboard or send alerts within a short delay (ideally a few seconds or less). Near-instant feedback is crucial for timely intrusion detection.
* **Privacy Preservation:** No personally identifiable or sensitive audio/visual data is collected. The solution should not violate privacy; it uses only radio signal information.
* **Reliability and Stability:** The system should run continuously and be robust against crashes or disconnects. It must handle continuous data streaming and logging without significant data loss. The logging of events should be persistent so that no records of detections are lost over time.
* **Accuracy and False Alarms:** The detection algorithm should be reasonably accurate in distinguishing real presence from noise. The system should minimize false positives (false alerts when no intruder is actually present) and false negatives (failing to detect an actual intruder). Calibration and good algorithm design will be important to meet this requirement.
* **Scalability (within scope):** For a typical deployment in a home or small office, the system should handle the necessary load (for example, one or a few sensor devices streaming data).

---

## External dependencies
The project relies on certain external hardware and software components:
* **Wi-Fi Hardware for CSI:** A Wi-Fi network interface capable of outputting Channel State Information is required.
* **CSI Extraction Tool/Software:** Specialized software is needed to capture CSI from the wireless interface.
* **Signal Processing and ML Libraries:** To process and analyze the CSI data, the system will use external libraries and possibly machine learning frameworks.
* **User Interface Platform:** The front-end interface will rely on external frameworks and platforms.

---

## Design

### High-Level Architecture
The Signally system consists of the following major subsystems:

**1. Back-End Architecture:**
* **Python with FastAPI** to handle a stream of continued logs and requests.
* **Scapy for python** to handle the Network Layer requests, probing and dissection of the packet information.
* **PostgreSQL database** to handle the long-term users of the app and approved members (household members) + information needed to be logged for a long time (intruder's address for police reports etc...).
* **Redis** in memory database that handles the quick and reliable information for real-time monitoring.

**2. Front-End Architecture:**
* **Mobile app** deployed using React-Native for cross-platform usage and responsive design.
* **TanStack Query** for local caching and fast lookup for responsive and quick user UI.
* **Supabase** as a middleman for communication with the backend hosted on the Raspberry Pi and the frontend.

### Components
The System main components:
* Raspberry Pi that connects to the ethernet network.
* Micro USB Wi-Fi adapter that connects to the raspberry pi to send probe requests to devices nearby.
* Micro SD card to host a Linux OS.

| Component | Role |
| :--- | :--- |
| **Raspberry Pi 4 / 5** | Central processing and hosting backend + CSI capture |
| **Wi-Fi adapter** | CSI extraction tool |
| **Micro SD** | Hosts OS and software |
| **Ethernet Cable & Power Supply** | Stable internet and power connections |

### Deployment
**Means of deployment:**
The product will run on a Raspberry Pi (4 or 5) connected to the home internet network via Ethernet for maximum stability. The Python / FastAPI backend will be deployed locally on the Pi as a background service; this ensures that high-velocity packet data is captured, filtered through Redis, and processed at the edge for immediate accuracy.

---

## Appendices

* **[Image Placeholder] Configuration sequence diagram:** Illustrates the two-phase setup mapping home borders and whitelisting devices.
* **[Image Placeholder] Friendly user sequence diagram:** Illustrates the signal disturbance workflow when a household member walks into a zone.
* **[Image Placeholder] Intruder sequence diagram:** Illustrates the event workflow when an unauthorized intruder enters the monitored space and triggers an alert.
* **[Image Placeholder] Architecture sketch:** Displays the layout of the Edge Server, Communication Layer, and User Interface.
* **[Image Placeholder] Wireframe sketch:** Shows the mobile UI for the dashboard, highlighting the security status and activity logs.
