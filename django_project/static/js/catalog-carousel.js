(() => {
    const carousels = document.querySelectorAll("[data-editorial-carousel]");
    const prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    carousels.forEach((carousel) => {
        const track = carousel.querySelector("[data-carousel-track]");
        const slides = Array.from(track.querySelectorAll("[data-carousel-slide]"));
        const previous = carousel.querySelector("[data-carousel-previous]");
        const next = carousel.querySelector("[data-carousel-next]");
        const count = carousel.querySelector("[data-carousel-count]");

        if (slides.length < 2 || !previous || !next || !count) {
            return;
        }

        let activeIndex = 0;
        let scrollFrame = 0;

        const updateControls = (index) => {
            activeIndex = index;
            slides.forEach((slide, slideIndex) => {
                slide.classList.toggle("is-current", slideIndex === activeIndex);
            });
            previous.disabled = activeIndex === 0;
            next.disabled = activeIndex === slides.length - 1;
            count.textContent = `${activeIndex + 1} / ${slides.length}`;
        };

        const goTo = (index) => {
            const targetIndex = Math.max(0, Math.min(index, slides.length - 1));
            if (targetIndex === activeIndex) {
                return;
            }

            updateControls(targetIndex);
            track.scrollTo({
                left: slides[targetIndex].offsetLeft,
                behavior: prefersReducedMotion ? "auto" : "smooth",
            });
        };

        previous.addEventListener("click", () => goTo(activeIndex - 1));
        next.addEventListener("click", () => goTo(activeIndex + 1));
        track.addEventListener("scroll", () => {
            if (scrollFrame) {
                window.cancelAnimationFrame(scrollFrame);
            }
            scrollFrame = window.requestAnimationFrame(() => {
                const index = slides.reduce(
                    (closestIndex, slide, candidateIndex) =>
                        Math.abs(slide.offsetLeft - track.scrollLeft) <
                        Math.abs(slides[closestIndex].offsetLeft - track.scrollLeft)
                            ? candidateIndex
                            : closestIndex,
                    0
                );
                updateControls(index);
            });
        });
    });
})();
