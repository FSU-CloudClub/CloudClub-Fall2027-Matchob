#include <deque>

class FrontMiddleBackQueue {
public:
    FrontMiddleBackQueue() = default;

    // Instruction: Insert at the requested position, and remove the front
    // middle element when the deque has two middle choices.
    // Keep every signature unchanged and do not add main() here.
    void pushFront(int val) {
        // Hint: a deque can expose both ends directly; the middle position is
        // computed from the current size before insertion.
        // TODO: implement your solution here
        values_.push_front(val);
    }

    void pushMiddle(int val) {
        // TODO: implement your solution here
        values_.insert(values_.begin() + static_cast<std::ptrdiff_t>(values_.size()) / 2, val);
    }

    void pushBack(int val) {
        // TODO: implement your solution here
        values_.push_back(val);
    }

    int popFront() {
        // TODO: implement your solution here
        if (values_.empty()) {
            return -1;
        }
        int front = values_.front();
        values_.pop_front();
        return front;
    }

    int popMiddle() {
        // TODO: implement your solution here
        if (values_.empty()) {
            return -1;
        }
        auto it = values_.begin() + static_cast<std::ptrdiff_t>((values_.size() - 1) / 2);
        int val = *it;
        values_.erase(it);
        return val;
    }

    int popBack() {
        // TODO: implement your solution here
        if (values_.empty()) {
            return -1;
        }
        int back = values_.back();
        values_.pop_back();
        return back;
    }

private:
    std::deque<int> values_;
};
