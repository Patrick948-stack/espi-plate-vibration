# espi_app/main.py - Application Entry Point

## Purpose

This is the main script that users run to start the entire application. It initializes PyQt6, loads saved settings, applies themes, and displays the landing page.

## How It Works (Step by Step)

### The main() function does the following:

1. Create a SettingsManager instance
   - This loads all saved settings from ~/.espi_app/settings.json
   - If this is the first run, it creates default settings

2. Create a PyQt6 QApplication instance
   - This is required before creating any GUI windows
   - It manages the event loop (handles button clicks, redraws, etc.)

3. Get the user's saved theme preference from settings
   - Theme can be "light" or "dark"

4. Apply the theme to the entire application
   - This changes colors, fonts, button styles globally

5. Create the LandingPage window
   - This is the first window the user sees
   - It lets them choose Monitor or Scan mode

6. Show the landing page window

7. Start the event loop
   - This keeps the application running
   - It processes user interactions (clicks, keyboard input)
   - The program doesn't exit until the user closes the window

## How to Run

From the command line, a user would run either:
```
python -m espi_app.main
```
or
```
python espi_app/main.py
```

## Why This Design

Separating the entry point into its own file makes it clear what happens when the app starts. By loading settings first, we can apply the user's saved theme immediately, so the window appears in their preferred style.

## Related Files

- settings.py - Manages loading and saving settings
- main_window.py - The LandingPage class
- styles.py - Theme and styling system
