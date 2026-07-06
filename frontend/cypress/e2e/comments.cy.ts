/// <reference types="cypress" />

const jordan = { id: 11, username: 'jordan', avatar_url: '/media/avatars/jordan.png', is_bot: false }
const gifgremlin = { id: 20, username: 'gifgremlin', avatar_url: '/media/avatars/gifgremlin.png', is_bot: true }
const maya = { id: 10, username: 'maya', avatar_url: '/media/avatars/maya.png', is_bot: false }

describe('comments', () => {
  beforeEach(() => {
    cy.intercept('GET', '/api/posts*', { fixture: 'feed.json' }).as('feed')
  })

  // Opens the comment thread on maya's post (comment_count = 2, like_count = 5).
  function openMayaThread() {
    cy.visitAs('maya')
    cy.wait('@feed')
    cy.contains('.MuiCard-root', 'switched to oat milk').within(() => {
      cy.contains('button', '2').click()
    })
  }

  it('expands a thread and renders a GIF-url comment as an inline image', () => {
    cy.intercept('GET', '/api/posts/2/comments', {
      statusCode: 200,
      body: [
        { id: 1, body: 'nice post', created_at: '2026-07-06T12:01:00Z', author: jordan },
        {
          id: 2,
          body: 'this is fine\nhttps://media3.giphy.com/media/abc/giphy.gif',
          created_at: '2026-07-06T12:02:00Z',
          author: gifgremlin,
        },
      ],
    }).as('comments')

    openMayaThread()
    cy.wait('@comments')

    cy.contains('nice post')
    cy.contains('this is fine')
    cy.get('img[alt="reaction gif"]')
      .should('have.attr', 'src')
      .and('include', 'giphy.gif')
  })

  it('adds a comment and shows it in the thread', () => {
    cy.intercept('GET', '/api/posts/2/comments', { statusCode: 200, body: [] }).as('comments')
    cy.intercept('POST', '/api/posts/2/comments', {
      statusCode: 200,
      body: { id: 3, body: 'great point', created_at: '2026-07-06T12:03:00Z', author: maya },
    }).as('addComment')

    openMayaThread()
    cy.wait('@comments')

    cy.contains('.MuiCard-root', 'switched to oat milk').within(() => {
      cy.get('input[placeholder*="giphy"]').type('great point')
      cy.contains('button', 'Reply').click()
    })

    cy.wait('@addComment')
    cy.contains('great point')
  })
})

export {}
