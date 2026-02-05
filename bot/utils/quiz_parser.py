import re


def parse_quiz_file(content: str) -> dict:
    """
    Parse quiz file content.

    Returns:
        {
            "title": "HTML",
            "topic": "HTML",
            "questions": [
                {
                    "text": "Какой тег создаёт ссылку?",
                    "option_a": "<link>",
                    "option_b": "<a>",
                    "option_c": "<href>",
                    "option_d": "<url>",
                    "correct": "B"
                },
                ...
            ]
        }

    Raises:
        ValueError: If format is invalid
    """
    lines = content.strip().split('\n')

    result = {
        "title": None,
        "topic": None,
        "questions": []
    }

    # Check for topic/title in first line
    if lines:
        first_line = lines[0].strip()
        topic_match = re.match(r'^(Тема|Topic|Tema):\s*(.+)$', first_line, re.IGNORECASE)
        if topic_match:
            result["topic"] = topic_match.group(2).strip()
            result["title"] = result["topic"]
            lines = lines[1:]

    # Join remaining content and split by question numbers
    content = '\n'.join(lines)

    # Pattern to match questions starting with number + optional difficulty markers (#/##) + dot
    # Examples: "1.", "2#.", "3##."
    question_pattern = r'(\d+)(#{1,2})?\.\s*(.+?)(?=\n\d+(?:#{1,2})?\.|$)'
    questions_raw = re.findall(question_pattern, content, re.DOTALL)

    if not questions_raw:
        raise ValueError("No questions found in file")

    for q_num, q_marks, q_content in questions_raw:
        q_lines = q_content.strip().split('\n')

        if len(q_lines) < 2:
            raise ValueError(f"Question {q_num} has insufficient content")

        # NEW LOGIC: Collect all lines until first option as question text
        question_lines = []
        option_start_index = None

        for i, line in enumerate(q_lines):
            line = line.strip()
            if not line:
                # Empty lines are part of question text (for spacing in code blocks)
                question_lines.append('')
                continue

            # Check if this line is an option (A), B), C), D))
            if re.match(r'^([A-D])(\*)?\)\s*', line, re.IGNORECASE):
                option_start_index = i
                break
            else:
                # This line is part of the question
                question_lines.append(line)

        if not question_lines:
            raise ValueError(f"Question {q_num} has no text")

        if option_start_index is None:
            raise ValueError(f"Question {q_num} has no options")

        # Join question lines (preserve line breaks for code blocks)
        question_text = '\n'.join(question_lines).strip()

        # Parse options starting from option_start_index
        options = {"A": None, "B": None, "C": None, "D": None}
        correct_answer = None

        for line in q_lines[option_start_index:]:
            line = line.strip()
            if not line:
                continue

            # Match options like "A)" or "A*)"
            option_match = re.match(r'^([A-D])(\*)?\)\s*(.+)$', line, re.IGNORECASE)
            if option_match:
                letter = option_match.group(1).upper()
                is_correct = option_match.group(2) == '*'
                option_text = option_match.group(3).strip()

                options[letter] = option_text
                if is_correct:
                    correct_answer = letter

        # Validate all options are present
        for letter in ["A", "B", "C", "D"]:
            if options[letter] is None:
                raise ValueError(f"Question {q_num} missing option {letter}")

        if correct_answer is None:
            raise ValueError(f"Question {q_num} has no correct answer marked with *")

        time_bonus = 0
        if q_marks == "#":
            time_bonus = 5
        elif q_marks == "##":
            time_bonus = 10

        result["questions"].append({
            "text": question_text,
            "option_a": options["A"],
            "option_b": options["B"],
            "option_c": options["C"],
            "option_d": options["D"],
            "correct": correct_answer,
            "time_bonus": time_bonus
        })

    if not result["questions"]:
        raise ValueError("No valid questions parsed")

    return result
