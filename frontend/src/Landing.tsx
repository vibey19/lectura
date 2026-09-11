import { Link } from "react-router-dom";
import { IconArrowRight, IconLayers, IconSparkle, IconWarn } from "./Icons";

/** Marketing page. Every number here is measured and reproducible from the
 *  committed evaluation set; none of it is aspirational. */
export default function Landing() {
  return (
    <div className="landing">
      <header className="nav">
        <Link to="/" className="brand" aria-label="Lectura home">
          <LogoMark />
          <span>Lectura</span>
        </Link>
        <nav>
          <a href="#how">How it works</a>
          <a href="#results">Results</a>
          <Link className="btn btn-primary btn-sm" to="/app">Open the app</Link>
        </nav>
      </header>

      <section className="hero">
        <p className="eyebrow">Lecture photographs into study notes</p>
        <h1>
          Your handwriting,<br />
          <em>set in type.</em>
        </h1>
        <p className="lede">
          Photograph a page of notes, a blackboard or a slide. Lectura reads the
          text <em>and</em> the mathematics, rebuilds the structure, and gives you
          notes you can edit, restyle and export — with every equation typeset.
        </p>
        <div className="hero-actions">
          <Link className="btn btn-primary btn-lg" to="/app">
            Try it on a photo <IconArrowRight size={17} />
          </Link>
          <a className="btn btn-ghost btn-lg" href="#results">See the measurements</a>
        </div>
        <TransformDemo />
      </section>

      <section id="how" className="section">
        <h2 className="section-title">How it works</h2>
        <ol className="steps">
          {[
            {
              n: "01",
              h: "It reads the page",
              p: "A vision model transcribes what is actually written — prose as prose, mathematics as LaTeX — without correcting or embellishing your notes.",
            },
            {
              n: "02",
              h: "It rebuilds the structure",
              p: "Headings, lists, definitions and equations become typed blocks in one canonical document, so the structure survives independently of how it looks.",
            },
            {
              n: "03",
              h: "You correct what it missed",
              p: "Recognition is good, not perfect. Every block is editable with a live preview, so fixing an exponent takes seconds instead of retyping the page.",
            },
          ].map((s) => (
            <li key={s.n}>
              <span className="step-n">{s.n}</span>
              <h3>{s.h}</h3>
              <p>{s.p}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="section alt">
        <h2 className="section-title">What makes it different</h2>
        <div className="cards">
          <article className="card">
            <IconLayers size={22} />
            <h3>Your notes stay yours</h3>
            <p>
              What was read off the page and what the model added are stored
              separately and shown differently. Nothing is silently rewritten.
            </p>
          </article>
          <article className="card">
            <IconWarn size={22} />
            <h3>It admits doubt</h3>
            <p>
              Uncertain blocks are flagged for review rather than presented as
              fact, and the source photograph sits beside the text so you can
              check anything against the original.
            </p>
          </article>
          <article className="card">
            <IconSparkle size={22} />
            <h3>One document, many looks</h3>
            <p>
              Themes are presentation over a single structured note. Switching
              between them is instant, because nothing is regenerated.
            </p>
          </article>
        </div>
      </section>

      <section id="results" className="section">
        <h2 className="section-title">Measured, not asserted</h2>
        <p className="section-lede">
          Scored against transcriptions written by hand from four real pages.
          Text and mathematics are measured separately, because ordinary OCR
          fails on notation long before it fails on prose.
        </p>
        <div className="table-wrap">
          <table className="results">
            <thead>
              <tr>
                <th scope="col">Approach</th>
                <th scope="col">Text error</th>
                <th scope="col">Formula error</th>
                <th scope="col">Exact formulas</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Classical OCR <span className="sub">Tesseract</span></th>
                <td>1.069</td><td>0.992</td><td>0 / 28</td>
              </tr>
              <tr>
                <th scope="row">Document pipeline <span className="sub">Pix2Text</span></th>
                <td>0.804</td><td>0.541</td><td>1 / 28</td>
              </tr>
              <tr className="best">
                <th scope="row">Lectura <span className="sub">Qwen2.5-VL 7B</span></th>
                <td>0.224</td><td>0.160</td><td>7 / 28</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="caveat">
          Lower is better. Four pages is enough to catch a large regression and
          not enough to settle anything — the set is growing, and these numbers
          move with it.
        </p>
      </section>

      <section className="cta">
        <h2>Bring a photo of your worst handwriting.</h2>
        <Link className="btn btn-primary btn-lg" to="/app">
          Open the app <IconArrowRight size={17} />
        </Link>
      </section>

      <footer className="foot">
        <LogoMark />
        <span>Lectura — runs on open weights, no paid inference API.</span>
      </footer>
    </div>
  );
}

function LogoMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="3" y="3" width="18" height="18" rx="5" fill="var(--accent)" />
      <path d="M8 8.5h8M8 12h8M8 15.5h4.5" stroke="var(--accent-ink)"
            strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

/** The product claim in one picture: a messy page becomes typeset notes. */
function TransformDemo() {
  return (
    <div className="demo" aria-hidden="true">
      <div className="demo-pane demo-before">
        <span className="demo-tag">photograph</span>
        <div className="scrawl">
          <span style={{ width: "58%" }} /><span style={{ width: "84%" }} />
          <span style={{ width: "71%" }} /><span className="tall" style={{ width: "46%" }} />
          <span style={{ width: "78%" }} /><span style={{ width: "62%" }} />
        </div>
      </div>
      <div className="demo-arrow"><IconArrowRight size={20} /></div>
      <div className="demo-pane demo-after">
        <span className="demo-tag">structured note</span>
        <h4>Problem 3</h4>
        <p className="demo-eq">√μ<sub>i</sub> = β<sub>0</sub> + β<sub>1</sub>x<sub>i</sub></p>
        <p className="demo-step">Square both sides</p>
        <p className="demo-eq">μ<sub>i</sub> = (β<sub>0</sub> + β<sub>1</sub>x<sub>i</sub>)²</p>
      </div>
    </div>
  );
}
