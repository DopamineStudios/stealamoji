const navHTML = `
<nav id="main-nav">
  <div class="container">
    <div class="logo">
      <img src="stealamoji.png" alt="Logo" class="logo-img">
      STEAL-A-MOJI
    </div>

    <button class="menu-toggle" aria-label="Toggle menu">
      <span></span>
      <span></span>
      <span></span>
    </button>

    <ul class="nav-links">
      <li><a href="index.html">Home</a></li>
      <li><a href="invite.html">Invite</a></li>
      <li><a href="https://status.dopaminestudios.in/">Bot Status</a></li>
      <div class="nav-underline"></div>
    </ul>
  </div>
</nav>
`;

function initializeNav() {
    document.body.insertAdjacentHTML('afterbegin', navHTML);

    const nav = document.getElementById('main-nav');
    const navLinks = document.querySelector('.nav-links');
    const menuToggle = document.querySelector('.menu-toggle');
    const underline = document.querySelector('.nav-underline');
    const allLinks = document.querySelectorAll('.nav-links a');

    const normalize = (path) => {
        if (!path) return "";
        return path.split("/").pop().replace(".html", "").replace("/", "") || "index";
    };

    let currentPath = normalize(window.location.pathname);
    let lastScrollY = window.scrollY;

    function moveUnderline(element, instant = false) {
        if (!element) return;

        if (instant) {
            underline.classList.add('no-transition');
        } else {
            underline.classList.remove('no-transition');
        }

        underline.style.width = `${element.offsetWidth}px`;
        underline.style.left = `${element.offsetLeft}px`;
        underline.style.opacity = "1";

        if (instant) {
            void underline.offsetWidth;
            underline.classList.remove('no-transition');
        }
    }

    allLinks.forEach(link => {
        const isInternal = link.getAttribute('href').includes('.html') || !link.getAttribute('href').startsWith('http');
        const linkPath = isInternal ? normalize(link.getAttribute('href')) : null;

        if (isInternal && linkPath === currentPath) {
            link.classList.add('active-link');
            setTimeout(() => moveUnderline(link, true), 50);
        }

        link.addEventListener('mouseenter', () => moveUnderline(link));

        link.addEventListener('click', () => {
            allLinks.forEach(l => l.classList.remove('active-link'));
            link.classList.add('active-link');
            moveUnderline(link);
        });
    });

    navLinks.addEventListener('mouseleave', () => {
        const activeLink = document.querySelector('.active-link');
        if (activeLink) moveUnderline(activeLink);
    });

    menuToggle.addEventListener('click', () => {
        menuToggle.classList.toggle('active');
        navLinks.classList.toggle('active');
    });

    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', () => {
            menuToggle.classList.remove('active');
            navLinks.classList.remove('active');
        });
    });

    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;
        if (currentScrollY > lastScrollY && currentScrollY > 100) {
            nav.classList.add('nav-hidden');
        } else {
            nav.classList.remove('nav-hidden');
        }
        nav.classList.toggle('nav-scrolled', currentScrollY > 10);
        lastScrollY = currentScrollY;
    });
}

document.addEventListener('DOMContentLoaded', initializeNav);
