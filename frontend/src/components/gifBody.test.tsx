import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { isGifUrl, renderBodyWithGifs } from './gifBody'

describe('isGifUrl', () => {
  it('matches direct .gif links and giphy hosts', () => {
    expect(isGifUrl('https://media3.giphy.com/media/abc/giphy.gif')).toBe(true)
    expect(isGifUrl('https://i.giphy.com/abc.gif')).toBe(true)
    expect(isGifUrl('  https://example.com/cat.gif?cid=1  ')).toBe(true)
  })

  it('does not match prose or non-gif urls', () => {
    expect(isGifUrl('mood')).toBe(false)
    expect(isGifUrl('check out https://example.com/cat.gif')).toBe(false)
    expect(isGifUrl('https://example.com/photo.png')).toBe(false)
  })
})

describe('renderBodyWithGifs', () => {
  it('renders a trailing gif-url line as a capped-width <img>', () => {
    const url = 'https://media3.giphy.com/media/abc/giphy.gif'
    render(<div>{renderBodyWithGifs(`mood\n${url}`)}</div>)

    expect(screen.getByText('mood')).toBeInTheDocument()
    const img = screen.getByAltText('reaction gif') as HTMLImageElement
    expect(img.tagName).toBe('IMG')
    expect(img.src).toBe(url)
  })

  it('leaves plain text untouched', () => {
    render(<div>{renderBodyWithGifs('just a normal comment')}</div>)

    expect(screen.getByText('just a normal comment')).toBeInTheDocument()
    expect(screen.queryByAltText('reaction gif')).toBeNull()
  })
})
