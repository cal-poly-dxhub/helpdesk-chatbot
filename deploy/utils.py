def ask_yes_no(prompt):
    """
    Prompt the user for a yes/no input with validation.
    """
    while True:
        answer = input(prompt + " (yes/no): ").strip().lower()
        if answer in ['yes', 'no']:
            return answer == 'yes'
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")